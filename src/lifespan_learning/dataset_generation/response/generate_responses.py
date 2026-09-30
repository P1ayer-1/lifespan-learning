"""Batch response generator: reads a prompt jsonl, calls the generation
model (GLM 5.3 through OpenRouter pinned to Baidu by default, or Claude
through the Message Batches API with --provider anthropic), and writes one
story per line in a frozen shape:

    {"prompt_hash": ..., "phase": ..., "tier": ..., "split": ...,
     "story": ..., "model": ..., "timestamp": ...}

`split` is copied from the prompt's own metadata.split (generate_prompts.py
writes it on every prompt). A corpus-wide registry (--corpus-registry /
--new-corpus-registry, see below) is REQUIRED on every run: it is the single
source of truth for "one model for the whole corpus" and, per --out file, for
which split lives there. Nothing about it is created silently.

Replaces `response/scratch.py` (a one-call Gemini-on-Vertex example with a
GCP project id hardcoded in source, superseded by the 2026-09-22 decision
to generate with Claude Haiku 4.5 -- see docs/DECISIONS.md in the Lifespan
repo). `scratch.py` itself is left untouched: it is the owner's own
uncommitted, staged work, not something this script edits or deletes.

Resumable: re-running skips prompt_hashes already written to --out, and a
batch already submitted (but not yet collected) is resumed from a small
state file next to --out rather than resubmitted -- a killed run costs
nothing extra. Retries with backoff apply only to retryable failures
(429, >=500, connection errors, and batch items whose error type is not
"invalid_request"); 4xx-shaped failures are never retried.

Usage:
    # Cost estimate only, no API call (no registry needed):
    python generate_responses.py --prompts train.jsonl --out train_stories.jsonl --dry-run

    # First run of a new corpus (declares the registry; must not already exist):
    python generate_responses.py --prompts train.jsonl --out train_stories.jsonl \
        --new-corpus-registry data/tier0/_generation_model.json --limit 20

    # Every later run against that corpus (registry must already exist and match):
    python generate_responses.py --prompts train.jsonl --out train_stories.jsonl \
        --corpus-registry data/tier0/_generation_model.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from lifespan_learning.dataset_generation.response.providers import (
    AnthropicBatchProvider,
    BatchRequestItem,
    BatchResultItem,
    FakeBatchProvider,
    StoryProvider,
    poll_until_ended,
)
from lifespan_learning.dataset_generation.response.openrouter_provider import OpenRouterProvider

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only when the SDK isn't installed
    anthropic = None

# 2026-09-23 (Lifespan docs/DECISIONS.md): the corpus generator is GLM 5.3 through
# OpenRouter, upstream pinned to Baidu (fp8), reasoning low. Chosen over Haiku 4.5
# in a blind 84-story head-to-head. The model string written to every story line
# carries upstream and quantization so a routing change cannot pass unnoticed.
DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "z-ai/glm-5.3"
DEFAULT_UPSTREAM = "Baidu"
DEFAULT_QUANTIZATION = "fp8"
DEFAULT_REASONING_EFFORT = "low"
ANTHROPIC_MODEL = "claude-haiku-4-5"  # the --provider anthropic default
# 2026-09-22 20-story smoke batch: max_tokens=900 truncated 4/20, including BOTH
# phase-6 stories (the longest, densest phase) -- a truncated story is a wasted
# request AND a forced retry, so 900 was actively more expensive than a higher
# cap, not cheaper. Raised to 2500; max_tokens is a ceiling, not a bill -- actual
# cost is metered on tokens generated, so this does not raise the cost estimate.
DEFAULT_MAX_TOKENS = 2500
# (input $/MTok, output $/MTok, batch discount) per provider; dry-run estimates only
PRICES = {
    "openrouter": (0.56, 1.76, 1.0),   # z-ai/glm-5.3 via Baidu on 2026-09-23; no batch discount exists
    "anthropic": (1.00, 5.00, 0.5),    # claude-haiku-4-5; the Message Batches API is half price
}
INPUT_PRICE_PER_MTOK_STANDARD, OUTPUT_PRICE_PER_MTOK_STANDARD, BATCH_DISCOUNT = PRICES["anthropic"]
# Re-derived 2026-09-23 for the story_prompt.py template (the "v2" A/B winner):
# measured mean output tokens per story on Haiku 4.5, 3 prompts per phase,
# seed 2 -- 525 across the 7 phases (the 2026-09-22 template measured 669 on
# the same prompts; the new one is shorter because it caps paragraphs and
# forbids the trailing moral). Input grew to ~540 tokens/prompt from ~200,
# which at $1/MTok is worth ~$0.03 per 1,000 stories; kept the 200-token
# CHARS_PER_TOKEN dry-run estimate honest by measuring, not assuming. 550
# leaves a small margin; per-phase means ranged 130 (phase 0) to ~730
# words (phase 6), equal weight per phase as in the real corpus.
ASSUMED_OUTPUT_TOKENS_PER_STORY = 550
CHARS_PER_TOKEN_ESTIMATE = 4  # rough, dry-run only; never used to bill anything

T = TypeVar("T")


# --------------------------------------------------------------------------
# Retry helper: retryable errors only (429, >=500, connection); never 4xx.
# --------------------------------------------------------------------------
def retry_call(fn: Callable[[], T], *, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if anthropic is not None:
                non_retryable = (
                    anthropic.BadRequestError,
                    anthropic.AuthenticationError,
                    anthropic.PermissionDeniedError,
                    anthropic.NotFoundError,
                )
                retryable = (
                    anthropic.RateLimitError,
                    anthropic.InternalServerError,
                    anthropic.APIConnectionError,
                )
                if isinstance(exc, non_retryable):
                    raise
                if not isinstance(exc, retryable):
                    raise
            else:
                raise  # no SDK loaded (e.g. FakeBatchProvider in tests): never blanket-retry

            attempt += 1
            if attempt > max_retries:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            print(
                f"Retryable error ({type(exc).__name__}): {exc}; "
                f"retrying in {delay:.1f}s (attempt {attempt}/{max_retries})",
                file=sys.stderr,
            )
            time.sleep(delay)


# --------------------------------------------------------------------------
# Story cleaning
# --------------------------------------------------------------------------
_TITLE_MAX_WORDS = 10


def clean_story(text: str) -> str:
    """Strip a leading title/heading and markdown emphasis from a story.

    Measured 2026-09-23 on the 2026-09-22 prompt template: Haiku 4.5 put a
    title line on 41 of 42 stories despite "Only use plain text". The new
    template gets that to 0/21 but this stays as the deterministic backstop:
    a title is a phase-uninformative artefact that would still land in the
    training text and in every held-out exam story.

    A first line counts as a title when it starts with '#' or is at most
    _TITLE_MAX_WORDS words with no sentence-ending punctuation, AND the rest
    of the text is non-empty. Only ever removes the first line; the story
    body is otherwise untouched apart from '**'/'__' emphasis markers and
    outer whitespace.
    """
    text = text.strip()
    lines = text.split("\n")
    if len(lines) > 1:
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        is_heading = first.startswith("#")
        is_short_untitled = (
            len(first.split()) <= _TITLE_MAX_WORDS
            and not first.rstrip().endswith((".", "!", "?", '"', "'", ",", ";", ":"))
        )
        if rest and (is_heading or is_short_untitled):
            text = rest
    text = text.replace("**", "").replace("__", "")
    return text.strip()


# --------------------------------------------------------------------------
# I/O helpers
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PromptRecord:
    prompt_hash: str
    prompt: str
    phase: int
    tier: int
    split: str


def load_prompts(path: Path) -> list[PromptRecord]:
    """Load a prompt jsonl. Refuses (hard exit) a file whose lines carry
    more than one metadata.split -- train and exam prompts must never be
    generated from the same file, which is what would let an exam prompt
    slip into a train --out with no other signal to catch it."""
    records = []
    splits_seen: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            metadata = row["metadata"]
            split = metadata["split"]
            splits_seen.add(split)
            records.append(
                PromptRecord(
                    prompt_hash=row["prompt_hash"],
                    prompt=row["prompt"],
                    phase=metadata["phase"],
                    tier=metadata["tier"],
                    split=split,
                )
            )
    if len(splits_seen) > 1:
        print(
            f"REFUSING: {path} mixes splits {sorted(splits_seen)!r} in one prompt file. "
            f"A prompt file must carry exactly one split throughout; generate train and "
            f"exam prompts into separate files and run this script once per file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return records


def existing_hashes_and_model(out_path: Path) -> tuple[set[str], set[str]]:
    """Prompt hashes already written, and EVERY model id found on ANY line
    (not just the last). A file written M2-then-M1 must be caught as mixed
    even though its last line looks fine -- collecting only the last line's
    model is exactly the bug that let that pass as M1."""
    hashes: set[str] = set()
    models: set[str] = set()
    if not out_path.exists():
        return hashes, models
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            hashes.add(row["prompt_hash"])
            m = row.get("model")
            if m is not None:
                models.add(m)
    return hashes, models


def existing_splits_in_file(path: Path) -> set[str]:
    """Every `split` value found on any line of a story file."""
    splits: set[str] = set()
    if not path.exists():
        return splits
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            s = row.get("split")
            if s is not None:
                splits.add(s)
    return splits


# Corpus files carry stories; these suffixes are OUR OWN sidecars living next
# to them and must never be mistaken for a phase file when scanning a
# directory for model ids.
NON_CORPUS_SUFFIXES = (
    ".failed.jsonl",
    ".regen_queue.jsonl",
    ".openrouter_cache.jsonl",
)
CORPUS_REGISTRY_NAME = "_generation_model.json"


def _is_corpus_file(path: Path) -> bool:
    name = path.name
    return not any(name.endswith(suffix) for suffix in NON_CORPUS_SUFFIXES)


def model_ids_in_directory(directory: Path) -> dict[str, set[str]]:
    """Map {file_name: {model ids}} for every corpus .jsonl file in
    `directory` (excluding our own .failed.jsonl / .regen_queue.jsonl
    sidecars) that has at least one line carrying a model id. A file's set
    has more than one member exactly when that file itself already mixes
    models (e.g. written M2-then-M1) -- that always conflicts, whatever
    model the current run wants, because there is no single model_id it
    could equal."""
    models: dict[str, set[str]] = {}
    if not directory.exists():
        return models
    for path in sorted(directory.glob("*.jsonl")):
        if not _is_corpus_file(path):
            continue
        _, file_models = existing_hashes_and_model(path)
        if file_models:
            models[path.name] = file_models
    return models


def split_ids_in_directory(directory: Path) -> dict[str, set[str]]:
    """Map {file_name: {split values}} for every corpus .jsonl file in
    `directory`, mirroring model_ids_in_directory."""
    splits: dict[str, set[str]] = {}
    if not directory.exists():
        return splits
    for path in sorted(directory.glob("*.jsonl")):
        if not _is_corpus_file(path):
            continue
        file_splits = existing_splits_in_file(path)
        if file_splits:
            splits[path.name] = file_splits
    return splits


def check_model_consistency(out_path: Path, model_id: str) -> None:
    """One model for every phase file in --out's directory. A model change
    within a directory (or a file that on its own already mixes models) is
    a confound the forgetting curve cannot separate from forgetting, so
    this is a hard exit, and the message never suggests picking a
    different --out -- that is exactly the move that would create the
    confound. The only correct remedies are to regenerate the whole corpus
    with one model, or to start a new corpus directory understood to be a
    new experiment (see --new-corpus-registry).
    """
    directory_models = model_ids_in_directory(out_path.parent)
    conflicting = {name: models for name, models in directory_models.items() if models != {model_id}}

    if conflicting:
        conflict_lines = "\n".join(
            f"  {name}: model(s)={sorted(models)!r}" for name, models in sorted(conflicting.items())
        )
        print(
            f"REFUSING to write: {out_path} would add model={model_id!r} to a directory that "
            f"already contains a different model:\n{conflict_lines}\n"
            f"One model for the whole corpus, train and exam alike. This is NOT fixed by "
            f"writing to a different --out -- either regenerate the whole corpus with one "
            f"model, or start a new corpus directory understood to be a new experiment.",
            file=sys.stderr,
        )
        sys.exit(1)


def check_split_consistency(out_path: Path, split: str, registry: dict) -> None:
    """--out never mixes splits: not with lines already written to it, and
    not with what the corpus registry already recorded for this exact file
    path (so even a deleted-and-regenerated file is still caught). Train
    and exam sharing one registry is by design (finding 2); this check is
    per-file, so it never conflicts with that."""
    conflicting: dict[str, set[str]] = {}

    directory_splits = split_ids_in_directory(out_path.parent)
    for name, splits in directory_splits.items():
        if splits != {split}:
            conflicting[name] = splits

    registry_files = registry.get("files", {})
    recorded = registry_files.get(str(out_path.resolve()))
    if recorded is not None and recorded != split:
        conflicting[f"registry record for {out_path}"] = {recorded}

    if conflicting:
        conflict_lines = "\n".join(
            f"  {name}: split(s)={sorted(splits)!r}" for name, splits in sorted(conflicting.items())
        )
        print(
            f"REFUSING to write: {out_path} would add split={split!r} but this location "
            f"already carries a different split:\n{conflict_lines}\n"
            f"Train and exam stories must never be combined in one file. Regenerate from "
            f"the correct split's prompt file instead.",
            file=sys.stderr,
        )
        sys.exit(1)


def load_or_create_registry(
    corpus_registry: Path | None,
    new_corpus_registry: Path | None,
    model_id: str,
) -> tuple[dict, Path]:
    """Load the corpus-wide registry (--corpus-registry, must already exist
    and its model must match) or create one (--new-corpus-registry, must
    NOT already exist). Exactly one is required on every run -- a registry
    is never created silently, and this function never suggests a way
    around passing one."""
    if corpus_registry is not None and new_corpus_registry is not None:
        print(
            "REFUSING: both --corpus-registry and --new-corpus-registry were given. "
            "Pass exactly one: --corpus-registry to continue an existing corpus, or "
            "--new-corpus-registry to start a new experiment's registry.",
            file=sys.stderr,
        )
        sys.exit(1)

    if new_corpus_registry is not None:
        if new_corpus_registry.exists():
            print(
                f"REFUSING: --new-corpus-registry {new_corpus_registry} already exists. "
                f"--new-corpus-registry declares a NEW experiment's registry and must not "
                f"already exist. Pass --corpus-registry {new_corpus_registry} instead to "
                f"continue the corpus already recorded there.",
                file=sys.stderr,
            )
            sys.exit(1)
        return {"model": model_id, "files": {}}, new_corpus_registry

    if corpus_registry is None:
        print(
            "REFUSING: no corpus registry given. Every run needs one: pass "
            "--corpus-registry <existing registry file> to continue this experiment's "
            "corpus, or --new-corpus-registry <path> to start a new one. A registry is "
            "never created silently.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not corpus_registry.exists():
        print(
            f"REFUSING: --corpus-registry {corpus_registry} does not exist. Pass "
            f"--new-corpus-registry {corpus_registry} instead if this is meant to start a "
            f"new experiment's registry.",
            file=sys.stderr,
        )
        sys.exit(1)

    registry = json.loads(corpus_registry.read_text(encoding="utf-8"))
    registry.setdefault("files", {})
    return registry, corpus_registry


def check_registry_model_consistency(registry: dict, registry_path: Path, model_id: str, out_path: Path) -> None:
    """One model for the whole corpus, train and exam alike, via the shared
    registry (catches a model change between splits, which live in
    different directories and so are invisible to check_model_consistency)."""
    registry_model = registry.get("model")
    if registry_model is not None and registry_model != model_id:
        print(
            f"REFUSING to write: {out_path} would add model={model_id!r} but the corpus "
            f"registry {registry_path} already records model={registry_model!r}.\n"
            f"One model for the whole corpus, train and exam alike. This is NOT fixed by "
            f"writing to a different --out -- either regenerate the whole corpus with one "
            f"model, or use --new-corpus-registry to start a new experiment's registry for "
            f"a genuinely different corpus.",
            file=sys.stderr,
        )
        sys.exit(1)
    registry["model"] = model_id


REGISTRY_LOCK_TIMEOUT_S = 60.0


def _acquire_registry_lock(lock_path: Path, timeout_s: float = REGISTRY_LOCK_TIMEOUT_S) -> int:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() > deadline:
                print(
                    f"REFUSING: the corpus registry lock {lock_path} has been held for over "
                    f"{timeout_s:.0f}s. If no other generation run is updating the registry, "
                    f"a killed run left it behind: delete {lock_path} and re-run.",
                    file=sys.stderr,
                )
                sys.exit(1)
            time.sleep(0.05)


def save_registry(registry_path: Path, registry: dict) -> None:
    """Merge this run's registry into the one on disk, under a lock.

    Runs launched in parallel each load the registry, add their own --out,
    and save. A plain write let the last saver erase the others' entries
    (2026-09-30: four output files lost this way). Now the save re-reads the
    file under an exclusive lock file, merges `files` (refusing a path
    recorded with a different split), refuses a different model, and
    replaces the file atomically.
    """
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = registry_path.with_name(registry_path.name + ".lock")
    fd = _acquire_registry_lock(lock_path)
    try:
        on_disk = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        disk_model, model = on_disk.get("model"), registry.get("model")
        if disk_model is not None and model is not None and disk_model != model:
            print(
                f"REFUSING to save the corpus registry {registry_path}: it now records "
                f"model={disk_model!r}, this run is model={model!r}. One model for the whole corpus.",
                file=sys.stderr,
            )
            sys.exit(1)
        files = dict(on_disk.get("files", {}))
        for path, split in registry.get("files", {}).items():
            if files.get(path, split) != split:
                print(
                    f"REFUSING to save the corpus registry {registry_path}: {path} is recorded "
                    f"as split={files[path]!r} and this run would record split={split!r}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            files[path] = split
        merged = {**on_disk, **registry, "files": files}
        tmp = registry_path.with_name(registry_path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, registry_path)
        registry.clear()
        registry.update(merged)
    finally:
        os.close(fd)
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass


def append_records(out_path: Path, records: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()


def append_failures(failed_path: Path, failures: list[dict]) -> None:
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    with failed_path.open("a", encoding="utf-8", newline="\n") as f:
        for failure in failures:
            f.write(json.dumps(failure, ensure_ascii=False) + "\n")


def load_batch_state(state_path: Path) -> dict | None:
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_batch_state(state_path: Path, state: dict) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def clear_batch_state(state_path: Path) -> None:
    if state_path.exists():
        state_path.unlink()


# --------------------------------------------------------------------------
# Cost estimate (dry run: no API call)
# --------------------------------------------------------------------------
# GLM 5.3 measured 690-720 output tokens a story on the same prompts (rounds
# r6/r7, ~80 of them reasoning), against Haiku's ~550.
ASSUMED_OUTPUT_TOKENS_BY_PROVIDER = {"openrouter": 700, "anthropic": ASSUMED_OUTPUT_TOKENS_PER_STORY}


def estimate_cost(prompts: list[PromptRecord], assumed_output_tokens: int | None = None, provider: str = "anthropic") -> dict:
    n = len(prompts)
    if assumed_output_tokens is None:
        assumed_output_tokens = ASSUMED_OUTPUT_TOKENS_BY_PROVIDER[provider]
    input_tokens = sum(max(1, len(p.prompt) // CHARS_PER_TOKEN_ESTIMATE) for p in prompts)
    output_tokens = n * assumed_output_tokens
    price_in, price_out, discount = PRICES[provider]

    input_cost_standard = input_tokens / 1_000_000 * price_in
    output_cost_standard = output_tokens / 1_000_000 * price_out
    input_cost_batch = input_cost_standard * discount
    output_cost_batch = output_cost_standard * discount

    return {
        "requests": n,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "standard_cost_usd": round(input_cost_standard + output_cost_standard, 2),
        "batch_cost_usd": round(input_cost_batch + output_cost_batch, 2),
    }


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------
def build_provider(
    model: str,
    fake_provider: StoryProvider | None,
    provider: str = DEFAULT_PROVIDER,
    out_path: Path | None = None,
    upstream: str = DEFAULT_UPSTREAM,
    quantization: str = DEFAULT_QUANTIZATION,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> StoryProvider:
    if fake_provider is not None:
        return fake_provider
    if provider == "anthropic":
        return AnthropicBatchProvider(model=model)
    if provider == "openrouter":
        if out_path is None:
            raise ValueError("the openrouter provider needs out_path for its resume cache")
        return OpenRouterProvider(
            cache_path=out_path.with_suffix(out_path.suffix + ".openrouter_cache.jsonl"),
            model=model,
            upstream=upstream,
            quantization=quantization,
            reasoning_effort=reasoning_effort,
        )
    raise ValueError(f"unknown provider {provider!r}")


def collect_batch(
    provider: StoryProvider,
    batch_id: str,
    prompt_by_hash: dict[str, PromptRecord],
    out_path: Path,
    failed_path: Path,
) -> tuple[int, list[str]]:
    """Collect a completed batch's results. Returns (written_count, retryable_hashes)."""
    written = 0
    to_write: list[dict] = []
    to_fail: list[dict] = []
    retryable_hashes: list[str] = []
    now = datetime.now(timezone.utc).isoformat()

    results: list[BatchResultItem] = retry_call(lambda: list(provider.batch_results(batch_id)))

    for result in results:
        prompt_record = prompt_by_hash.get(result.custom_id)
        if prompt_record is None:
            continue  # not one of ours (shouldn't happen, but never crash on it)

        if result.outcome == "succeeded":
            to_write.append(
                {
                    "prompt_hash": result.custom_id,
                    "phase": prompt_record.phase,
                    "tier": prompt_record.tier,
                    "split": prompt_record.split,
                    "story": clean_story(result.text or ""),
                    "model": provider.model_id,
                    "timestamp": now,
                }
            )
            written += 1
        elif result.retryable:
            retryable_hashes.append(result.custom_id)
        else:
            to_fail.append(
                {
                    "prompt_hash": result.custom_id,
                    "outcome": result.outcome,
                    "error": result.error_message,
                    "timestamp": now,
                }
            )

    append_records(out_path, to_write)
    if to_fail:
        append_failures(failed_path, to_fail)

    return written, retryable_hashes


def run(
    prompts_path: Path,
    out_path: Path,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    limit: int | None = None,
    max_batch_retries: int = 3,
    poll_seconds: float = 20.0,
    poll_timeout: float = 3600.0,
    fake_provider: StoryProvider | None = None,
    corpus_registry: Path | None = None,
    new_corpus_registry: Path | None = None,
    provider_name: str = DEFAULT_PROVIDER,
    upstream: str = DEFAULT_UPSTREAM,
    quantization: str = DEFAULT_QUANTIZATION,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict:
    # Prompts first (no credentials needed): refuses a mixed-split prompt file
    # before anything else happens.
    prompts = load_prompts(prompts_path)
    prompt_by_hash = {p.prompt_hash: p for p in prompts}
    split = prompts[0].split if prompts else None

    provider = build_provider(model, fake_provider, provider_name, out_path, upstream, quantization, reasoning_effort)

    registry, registry_path = load_or_create_registry(corpus_registry, new_corpus_registry, provider.model_id)
    # Directory-level model check first: it names the two conflicting files
    # directly, which the registry-level check (next) cannot -- run it before
    # the registry check so that message wins when both would fire.
    check_model_consistency(out_path, provider.model_id)
    check_registry_model_consistency(registry, registry_path, provider.model_id, out_path)
    if split is not None:
        check_split_consistency(out_path, split, registry)
        registry.setdefault("files", {})[str(out_path.resolve())] = split
    save_registry(registry_path, registry)

    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    failed_path = out_path.with_suffix(out_path.suffix + ".failed.jsonl")

    written_total = 0
    skipped_total = 0
    failed_total = 0

    # 1. Resume an in-flight batch, if one was persisted by a previous (killed) run.
    # A state file can also hold pending_retry_hashes with batch_id=None (written at
    # the end of a previous run that had retryable failures but hadn't resubmitted
    # them yet) -- that is NOT an in-flight batch, so there is nothing to poll; fall
    # through to step 2, which submits a fresh batch for those hashes.
    state = load_batch_state(state_path)
    if state is not None and state.get("batch_id"):
        print(f"Resuming in-flight batch {state['batch_id']} ({len(state['custom_ids'])} requests)...")
        if hasattr(provider, "resume_items"):
            # a synchronous provider (OpenRouter) needs the prompts again to finish a batch a killed run left behind
            provider.resume_items(
                [BatchRequestItem(custom_id=h, prompt=prompt_by_hash[h].prompt) for h in state["custom_ids"] if h in prompt_by_hash],
                max_tokens,
            )
        status = retry_call(lambda: poll_until_ended(provider, state["batch_id"], poll_seconds, poll_timeout))
        if status.processing_status == "ended":
            written, retryable_hashes = collect_batch(provider, state["batch_id"], prompt_by_hash, out_path, failed_path)
            written_total += written
            clear_batch_state(state_path)
            if retryable_hashes:
                state = {"pending_retry_hashes": retryable_hashes, "retry_attempt": state.get("retry_attempt", 0)}
            else:
                state = None
        else:
            print(
                f"Batch {state['batch_id']} still {status.processing_status} after "
                f"{poll_timeout:.0f}s; re-run this command later to resume collecting it.",
            )
            return {"written": written_total, "skipped": 0, "failed": 0, "pending_batch": state["batch_id"]}

    # 2. Figure out what's left to do: anything not already in --out, plus any
    #    retryable hashes carried over from a batch we just collected.
    existing_hashes, _ = existing_hashes_and_model(out_path)
    skipped_total = len(existing_hashes)

    retry_attempt = 0
    pending_retry_hashes: list[str] = []
    if state is not None:
        pending_retry_hashes = state.get("pending_retry_hashes", [])
        retry_attempt = state.get("retry_attempt", 0)

    if pending_retry_hashes:
        missing_hashes = pending_retry_hashes
    else:
        missing_hashes = [p.prompt_hash for p in prompts if p.prompt_hash not in existing_hashes]

    if limit is not None:
        missing_hashes = missing_hashes[:limit]

    if not missing_hashes:
        return {"written": written_total, "skipped": skipped_total, "failed": failed_total}

    if retry_attempt >= max_batch_retries:
        append_failures(
            failed_path,
            [
                {"prompt_hash": h, "outcome": "gave_up", "error": f"exceeded {max_batch_retries} retries"}
                for h in missing_hashes
            ],
        )
        return {"written": written_total, "skipped": skipped_total, "failed": len(missing_hashes)}

    # 3. Submit a batch for whatever's left.
    items = [BatchRequestItem(custom_id=h, prompt=prompt_by_hash[h].prompt) for h in missing_hashes]
    batch_id = retry_call(lambda: provider.submit_batch(items, max_tokens))
    save_batch_state(
        state_path,
        {
            "batch_id": batch_id,
            "custom_ids": missing_hashes,
            "model": provider.model_id,
            "retry_attempt": retry_attempt,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    print(f"Submitted batch {batch_id} ({len(items)} requests).")

    status = retry_call(lambda: poll_until_ended(provider, batch_id, poll_seconds, poll_timeout))
    if status.processing_status != "ended":
        print(
            f"Batch {batch_id} still {status.processing_status} after {poll_timeout:.0f}s; "
            "re-run this command later to resume collecting it.",
        )
        return {"written": written_total, "skipped": skipped_total, "failed": 0, "pending_batch": batch_id}

    written, retryable_hashes = collect_batch(provider, batch_id, prompt_by_hash, out_path, failed_path)
    written_total += written
    clear_batch_state(state_path)

    if retryable_hashes:
        save_batch_state(
            state_path,
            {"pending_retry_hashes": retryable_hashes, "retry_attempt": retry_attempt + 1, "batch_id": None, "custom_ids": []},
        )
        print(f"{len(retryable_hashes)} retryable failures queued for the next run.")

    failed_total = len(missing_hashes) - written - len(retryable_hashes)
    return {"written": written_total, "skipped": skipped_total, "failed": failed_total}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate story responses for a prompt jsonl via the Claude Batch API.")
    parser.add_argument("--prompts", type=Path, required=True, help="Input prompt jsonl (from generate_prompts.py).")
    parser.add_argument("--out", type=Path, required=True, help="Output story jsonl (resumable: existing prompt_hashes are skipped).")
    parser.add_argument("--model", type=str, default=None, help=f"Model id (default: {DEFAULT_MODEL} for openrouter, {ANTHROPIC_MODEL} for anthropic).")
    parser.add_argument("--provider", type=str, default=DEFAULT_PROVIDER, choices=sorted(PRICES), help="openrouter (GLM 5.3, default) or anthropic (Claude Message Batches API).")
    parser.add_argument("--upstream", type=str, default=DEFAULT_UPSTREAM, help="OpenRouter upstream to pin (default Baidu); fallbacks are disabled.")
    parser.add_argument("--quantization", type=str, default=DEFAULT_QUANTIZATION, help="Recorded in the model string for provenance (default fp8).")
    parser.add_argument("--reasoning-effort", type=str, default=DEFAULT_REASONING_EFFORT, dest="reasoning_effort", help="OpenRouter reasoning effort (default low; GLM 5.3 cannot run with reasoning off).")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, dest="max_tokens")
    parser.add_argument("--limit", type=int, default=None, help="Cap on new requests this run (use <=20 for a smoke batch).")
    parser.add_argument("--max-batch-retries", type=int, default=3, dest="max_batch_retries")
    parser.add_argument("--poll-seconds", type=float, default=20.0, dest="poll_seconds")
    parser.add_argument("--poll-timeout", type=float, default=3600.0, dest="poll_timeout")
    parser.add_argument("--dry-run", action="store_true", help="Print request count and estimated cost; make no API call.")
    parser.add_argument(
        "--corpus-registry",
        type=Path,
        default=None,
        dest="corpus_registry",
        help=(
            "Existing corpus-wide registry file (shared across train and exam) that this "
            "run's model must match. Required unless --new-corpus-registry is given; never "
            "created automatically."
        ),
    )
    parser.add_argument(
        "--new-corpus-registry",
        type=Path,
        default=None,
        dest="new_corpus_registry",
        help=(
            f"Path for a brand-new {CORPUS_REGISTRY_NAME!r}-style registry that declares a "
            "new experiment's corpus; must not already exist. Use this exactly once, for "
            "the first run of a new corpus; every later run against it uses --corpus-registry."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # A failure that reports success is worse than a crash: nothing downstream
    # (a resumed run, a caller script, the lead deciding whether to spend more)
    # can tell it failed. Every path below either returns normally or calls
    # sys.exit(1) -- never lets an exception escape with the interpreter's
    # default (and here, apparently unreliable) exit-code behaviour.
    model = args.model or (DEFAULT_MODEL if args.provider == "openrouter" else ANTHROPIC_MODEL)
    try:
        if args.dry_run:
            existing_hashes, _ = existing_hashes_and_model(args.out)
            prompts = load_prompts(args.prompts)
            missing = [p for p in prompts if p.prompt_hash not in existing_hashes]
            if args.limit is not None:
                missing = missing[: args.limit]
            estimate = estimate_cost(missing, provider=args.provider)
            print(f"Dry run: {estimate['requests']} requests would be submitted (model={model}, provider={args.provider}).")
            print(f"  estimated input tokens:  {estimate['estimated_input_tokens']:,}")
            print(f"  estimated output tokens: {estimate['estimated_output_tokens']:,} (at {ASSUMED_OUTPUT_TOKENS_BY_PROVIDER[args.provider]}/story)")
            print(f"  estimated cost, standard API: ${estimate['standard_cost_usd']:.2f}")
            print(f"  estimated cost, Batch API:    ${estimate['batch_cost_usd']:.2f}" + ("" if args.provider == "anthropic" else " (no batch discount on openrouter; same as standard)"))
            return

        summary = run(
            prompts_path=args.prompts,
            out_path=args.out,
            model=model,
            max_tokens=args.max_tokens,
            limit=args.limit,
            max_batch_retries=args.max_batch_retries,
            poll_seconds=args.poll_seconds,
            poll_timeout=args.poll_timeout,
            corpus_registry=args.corpus_registry,
            new_corpus_registry=args.new_corpus_registry,
            provider_name=args.provider,
            upstream=args.upstream,
            quantization=args.quantization,
            reasoning_effort=args.reasoning_effort,
        )
        print(f"written={summary['written']} skipped={summary['skipped']} failed={summary['failed']}")
        if summary.get("pending_batch"):
            print(f"Batch {summary['pending_batch']} still processing; re-run to resume.")
    except SystemExit:
        raise  # an explicit, already-correct exit code (e.g. the split/model refusals)
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
