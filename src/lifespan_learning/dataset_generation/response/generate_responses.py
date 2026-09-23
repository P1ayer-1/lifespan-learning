"""Batch response generator: reads a prompt jsonl, calls the generation
model through the Claude Message Batches API, and writes one story per
line in a frozen shape:

    {"prompt_hash": ..., "phase": ..., "tier": ..., "story": ...,
     "model": ..., "timestamp": ...}

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
    # Cost estimate only, no API call:
    python generate_responses.py --prompts train.jsonl --out train_stories.jsonl --dry-run

    # Smoke batch (max 20 -- see the spend gate in this project's brief):
    python generate_responses.py --prompts train.jsonl --out smoke.jsonl --limit 20

    # Real run (the lead runs this after the owner says yes):
    python generate_responses.py --prompts train.jsonl --out train_stories.jsonl
"""
from __future__ import annotations

import argparse
import json
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

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only when the SDK isn't installed
    anthropic = None

DEFAULT_MODEL = "claude-haiku-4-5"
# 2026-09-22 20-story smoke batch: max_tokens=900 truncated 4/20, including BOTH
# phase-6 stories (the longest, densest phase) -- a truncated story is a wasted
# request AND a forced retry, so 900 was actively more expensive than a higher
# cap, not cheaper. Raised to 2500; max_tokens is a ceiling, not a bill -- actual
# cost is metered on tokens generated, so this does not raise the cost estimate.
DEFAULT_MAX_TOKENS = 2500
INPUT_PRICE_PER_MTOK_STANDARD = 1.00
OUTPUT_PRICE_PER_MTOK_STANDARD = 5.00
BATCH_DISCOUNT = 0.5  # Message Batches API is half the standard price
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


def load_prompts(path: Path) -> list[PromptRecord]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            metadata = row["metadata"]
            records.append(
                PromptRecord(
                    prompt_hash=row["prompt_hash"],
                    prompt=row["prompt"],
                    phase=metadata["phase"],
                    tier=metadata["tier"],
                )
            )
    return records


def existing_hashes_and_model(out_path: Path) -> tuple[set[str], str | None]:
    """Prompt hashes already written, and the model id already on record (if any)."""
    hashes: set[str] = set()
    model: str | None = None
    if not out_path.exists():
        return hashes, model
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            hashes.add(row["prompt_hash"])
            model = row.get("model", model)
    return hashes, model


# Corpus files carry stories; these suffixes are OUR OWN sidecars living next
# to them and must never be mistaken for a phase file when scanning a
# directory for model ids.
NON_CORPUS_SUFFIXES = (".failed.jsonl", ".regen_queue.jsonl")
CORPUS_REGISTRY_NAME = "_generation_model.json"


def _is_corpus_file(path: Path) -> bool:
    name = path.name
    return not any(name.endswith(suffix) for suffix in NON_CORPUS_SUFFIXES)


def model_ids_in_directory(directory: Path) -> dict[str, str]:
    """Map {file_name: model_id} for every corpus .jsonl file in `directory`
    (excluding our own .failed.jsonl / .regen_queue.jsonl sidecars) that has
    at least one line carrying a model id."""
    models: dict[str, str] = {}
    if not directory.exists():
        return models
    for path in sorted(directory.glob("*.jsonl")):
        if not _is_corpus_file(path):
            continue
        _, model = existing_hashes_and_model(path)
        if model is not None:
            models[path.name] = model
    return models


def default_registry_path(out_path: Path) -> Path:
    """Where the cross-split model registry lives by default: one level
    above the split directory (out_path.parent), i.e. the corpus root a
    train/ and exam/ directory would share as siblings. Pass
    --corpus-registry explicitly if train and exam don't share a parent."""
    return out_path.parent.parent / CORPUS_REGISTRY_NAME


def check_model_consistency(out_path: Path, model_id: str, registry_path: Path | None = None) -> None:
    """One model for the WHOLE corpus -- every phase file in --out's
    directory, AND, via a small shared registry file, every split (train
    and exam alike). A model change anywhere in here is a confound the
    forgetting curve cannot separate from forgetting, so this is a hard
    exit, and the message never suggests picking a different --out --
    that is exactly the move that would create the confound. The only
    correct remedies are to regenerate the whole corpus with one model, or
    to start a new corpus directory understood to be a new experiment.
    """
    directory = out_path.parent

    # 1. Within this directory (catches a model change between phase files
    #    of the same split, e.g. train_phase_3.jsonl vs train_phase_4.jsonl).
    directory_models = model_ids_in_directory(directory)
    conflicting = {name: mid for name, mid in directory_models.items() if mid != model_id}

    # 2. Across splits, via the shared registry (catches train vs exam).
    registry_path = registry_path or default_registry_path(out_path)
    registry_model = None
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_model = registry.get("model")
        if registry_model is not None and registry_model != model_id:
            conflicting[str(registry_path)] = registry_model

    if conflicting:
        conflict_lines = "\n".join(f"  {name}: model={mid!r}" for name, mid in sorted(conflicting.items()))
        print(
            f"REFUSING to write: {out_path} would add model={model_id!r} to a corpus that "
            f"already contains a different model:\n{conflict_lines}\n"
            f"One model for the whole corpus, train and exam alike. This is NOT fixed by "
            f"writing to a different --out -- either regenerate the whole corpus with one "
            f"model, or start a new corpus directory understood to be a new experiment.",
            file=sys.stderr,
        )
        sys.exit(1)

    if registry_model is None:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps({"model": model_id}, indent=2) + "\n", encoding="utf-8", newline="\n")


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
def estimate_cost(prompts: list[PromptRecord], assumed_output_tokens: int = ASSUMED_OUTPUT_TOKENS_PER_STORY) -> dict:
    n = len(prompts)
    input_tokens = sum(max(1, len(p.prompt) // CHARS_PER_TOKEN_ESTIMATE) for p in prompts)
    output_tokens = n * assumed_output_tokens

    input_cost_standard = input_tokens / 1_000_000 * INPUT_PRICE_PER_MTOK_STANDARD
    output_cost_standard = output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MTOK_STANDARD
    input_cost_batch = input_cost_standard * BATCH_DISCOUNT
    output_cost_batch = output_cost_standard * BATCH_DISCOUNT

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
def build_provider(model: str, fake_provider: StoryProvider | None) -> StoryProvider:
    if fake_provider is not None:
        return fake_provider
    return AnthropicBatchProvider(model=model)


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
    registry_path: Path | None = None,
) -> dict:
    provider = build_provider(model, fake_provider)
    check_model_consistency(out_path, provider.model_id, registry_path)

    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    failed_path = out_path.with_suffix(out_path.suffix + ".failed.jsonl")

    prompts = load_prompts(prompts_path)
    prompt_by_hash = {p.prompt_hash: p for p in prompts}

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
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Model id (default: {DEFAULT_MODEL}).")
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
            "Shared cross-split model registry file. Defaults to a "
            f"{CORPUS_REGISTRY_NAME!r} file one directory above --out (the corpus root "
            "a train/ and exam/ directory would share as siblings). Pass this explicitly "
            "if train and exam don't share a parent directory."
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
    try:
        if args.dry_run:
            existing_hashes, _ = existing_hashes_and_model(args.out)
            prompts = load_prompts(args.prompts)
            missing = [p for p in prompts if p.prompt_hash not in existing_hashes]
            if args.limit is not None:
                missing = missing[: args.limit]
            estimate = estimate_cost(missing)
            print(f"Dry run: {estimate['requests']} requests would be submitted (model={args.model}).")
            print(f"  estimated input tokens:  {estimate['estimated_input_tokens']:,}")
            print(f"  estimated output tokens: {estimate['estimated_output_tokens']:,} (at {ASSUMED_OUTPUT_TOKENS_PER_STORY}/story)")
            print(f"  estimated cost, standard API: ${estimate['standard_cost_usd']:.2f}")
            print(f"  estimated cost, Batch API:    ${estimate['batch_cost_usd']:.2f}")
            return

        summary = run(
            prompts_path=args.prompts,
            out_path=args.out,
            model=args.model,
            max_tokens=args.max_tokens,
            limit=args.limit,
            max_batch_retries=args.max_batch_retries,
            poll_seconds=args.poll_seconds,
            poll_timeout=args.poll_timeout,
            registry_path=args.corpus_registry,
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
