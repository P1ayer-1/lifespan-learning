# generate_prompts.py
"""Entry point for generating curriculum-learning prompts.

Must be run with the current working directory set to this file's directory
(`prompt/`), because the engine's config loaders resolve paths like
"config/phases.yaml" relative to cwd -- that is pre-existing behaviour of
`PromptDatasetGenerator`/`config_loader.py`, not something this script
changes.

Examples:
    python generate_prompts.py --split train --seed 42   --per-phase 5000 --out data/train_prompts.jsonl
    python generate_prompts.py --split exam  --seed 4242 --per-phase 500  --out data/exam_prompts.jsonl
    python generate_prompts.py --split train --seed 42 --phases 0,1,2 --per-phase 100 --out /tmp/smoke.jsonl

`split` ("train" or "exam") is written into every prompt's metadata, and is
also the first line of defence against exam/train contamination: this
script refuses to write to an --out path that already holds prompts from
the other split (see `check_split_refusal`). An exam run should always use
its own seed and its own --out path, never one a training run has touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from lifespan_learning.dataset_generation.prompt.engine import PromptDatasetGenerator


def compute_prompt_hash(prompt_text: str, metadata: dict) -> str:
    """Deterministic hash of a prompt's full identity (text + metadata).

    Depends only on the prompt text and its metadata (which already
    includes split/phase/tier/seed-derived content), never on wall clock,
    dict iteration order (json.dumps(..., sort_keys=True) fixes that) or
    anything else non-deterministic. Same seed and config -> same hash,
    byte for byte, on any machine. This is the `prompt_hash` the response
    generator uses as its resume/dedupe key and Batch API `custom_id`.
    """
    canonical = json.dumps(
        {"prompt": prompt_text, "metadata": metadata},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_phase_ids(phases_arg: str | None, available_ids: list[int]) -> list[int]:
    """Parse --phases into an ordered list of ids, validated against what exists."""
    if not phases_arg:
        return available_ids
    requested = [int(p.strip()) for p in phases_arg.split(",") if p.strip() != ""]
    unknown = sorted(set(requested) - set(available_ids))
    if unknown:
        raise SystemExit(f"Unknown phase id(s) {unknown}; available phase ids: {available_ids}")
    return requested


def _first_record_split(out_path: Path) -> str | None:
    """Return the split recorded in an existing output file's first line, or None."""
    if not out_path.exists() or out_path.stat().st_size == 0:
        return None
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            return record.get("metadata", {}).get("split")
    return None


def check_split_refusal(out_path: Path, split: str) -> None:
    """Hard exit if --out already holds prompts from the OTHER split.

    This is the first line of defence for the whole experiment's validity:
    training data and exam data must never land in the same file, or a
    training run could leak into what is supposed to be a held-out exam,
    silently invalidating every exam score. Writing more of the SAME split
    to an existing file is allowed (e.g. resuming or regenerating a split);
    only a split mismatch is refused.
    """
    existing_split = _first_record_split(out_path)
    if existing_split is not None and existing_split != split:
        print(
            f"REFUSING to write: {out_path} already contains split={existing_split!r} "
            f"prompts, but this run requested split={split!r}. Train and exam data "
            f"must never share an output path. Pick a different --out.",
            file=sys.stderr,
        )
        sys.exit(1)


def _generator_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate curriculum-learning prompts.")
    parser.add_argument(
        "--split",
        required=True,
        choices=["train", "exam"],
        help="Which split these prompts belong to. Written into every prompt's metadata.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed. Same seed + config -> byte-identical prompts. Exam runs must use a seed distinct from the train run's.",
    )
    parser.add_argument(
        "--per-phase",
        type=int,
        default=1000,
        dest="per_phase",
        help="Number of prompts to generate per phase (default: 1000).",
    )
    parser.add_argument(
        "--phases",
        type=str,
        default=None,
        help="Comma-separated phase ids to generate, e.g. '0,1,2'. Default: all phases in phases.yaml.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output .jsonl path. Refused if it already holds prompts from the other split.",
    )
    return parser


def generate(args: argparse.Namespace) -> list[dict]:
    generator = PromptDatasetGenerator(seed=args.seed)
    available_ids = [phase.config["id"] for phase in generator.phases]
    wanted_ids = parse_phase_ids(args.phases, available_ids)

    records: list[dict] = []
    for phase in generator.phases:
        phase_id = phase.config["id"]
        if phase_id not in wanted_ids:
            continue
        print(f"Generating {args.per_phase} prompts for phase {phase_id}: {phase.config['name']}")
        phase_prompts = phase.generate_prompts(args.per_phase)
        for prompt in phase_prompts:
            prompt["metadata"]["split"] = args.split
            prompt_hash = compute_prompt_hash(prompt["prompt"], prompt["metadata"])
            records.append({"prompt_hash": prompt_hash, **prompt})

    return records


def save_records(records: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8, "\n" newlines explicitly: hashes/line-diffs must match across
    # Windows and Linux (Kaggle), not just the JSON content.
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_sidecar(records: list[dict], out_path: Path, args: argparse.Namespace) -> None:
    counts_per_phase: dict[str, int] = {}
    for record in records:
        phase_id = str(record["metadata"]["phase"])
        counts_per_phase[phase_id] = counts_per_phase.get(phase_id, 0) + 1

    sidecar = {
        "generator_commit": _generator_commit(),
        "split": args.split,
        "seed": args.seed,
        "per_phase": args.per_phase,
        "phases_requested": args.phases,
        "total_prompts": len(records),
        "counts_per_phase": counts_per_phase,
    }
    sidecar_path = out_path.with_suffix(out_path.suffix + ".sidecar.json")
    with sidecar_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(sidecar, f, indent=2, sort_keys=True)
        f.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    check_split_refusal(args.out, args.split)

    records = generate(args)
    save_records(records, args.out)
    save_sidecar(records, args.out, args)

    print(f"Wrote {len(records)} prompts (split={args.split}) to {args.out}")


if __name__ == "__main__":
    main()
