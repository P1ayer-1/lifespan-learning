"""One-off, idempotent migration: write split="train" into the Tier 0 story
files that predate the split field (2026-09-25 leakage audit, finding 1).

For each (stories, prompts) pair below, every story line's prompt_hash is
verified against the prompts file's own metadata.split (must be "train")
before the story line is touched -- this never invents a split, it only
copies one already on record. A line that already carries "split" is left
alone (idempotent: safe to re-run). A prompt_hash with no match in its
prompts file, or a match whose metadata.split isn't "train", stops the
migration for that file with a clear error and touches nothing.

    python tools/migrate_tier0_split.py            # apply
    python tools/migrate_tier0_split.py --check     # verify only, no writes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (stories file, prompts file it must be verified against)
PAIRS = [
    (ROOT / "data" / "tier0" / "full" / "stories.jsonl", ROOT / "data" / "tier0" / "train" / "prompts.jsonl"),
    (ROOT / "data" / "tier0" / "regen1" / "stories.jsonl", ROOT / "data" / "tier0" / "regen1" / "prompts.jsonl"),
    (ROOT / "data" / "tier0" / "regen2" / "stories.jsonl", ROOT / "data" / "tier0" / "regen2" / "prompts.jsonl"),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_prompt_splits(prompts_path: Path) -> dict[str, str]:
    """{prompt_hash: metadata.split} for every prompt in prompts_path."""
    splits: dict[str, str] = {}
    with prompts_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            splits[row["prompt_hash"]] = row["metadata"]["split"]
    return splits


def migrate_file(stories_path: Path, prompts_path: Path, *, check_only: bool) -> tuple[str, str, int, int]:
    """Returns (sha256_before, sha256_after, lines_total, lines_changed)."""
    if not stories_path.exists():
        raise FileNotFoundError(stories_path)
    if not prompts_path.exists():
        raise FileNotFoundError(prompts_path)

    sha_before = sha256_of(stories_path)
    prompt_splits = load_prompt_splits(prompts_path)

    out_lines: list[str] = []
    changed = 0
    total = 0
    with stories_path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw_stripped = raw.strip()
            if not raw_stripped:
                continue
            total += 1
            row = json.loads(raw_stripped)
            if "split" in row:
                out_lines.append(json.dumps(row, ensure_ascii=False))
                continue

            prompt_hash = row["prompt_hash"]
            split = prompt_splits.get(prompt_hash)
            if split is None:
                raise ValueError(
                    f"{stories_path}: prompt_hash {prompt_hash!r} has no match in {prompts_path} "
                    f"-- refusing to guess a split for it."
                )
            if split != "train":
                raise ValueError(
                    f"{stories_path}: prompt_hash {prompt_hash!r} is recorded as split={split!r} "
                    f"in {prompts_path}, not 'train' -- refusing to mislabel it."
                )

            # Insert split right after tier, matching the frozen story shape
            # {prompt_hash, phase, tier, split, story, model, timestamp}.
            new_row = {}
            inserted = False
            for key, value in row.items():
                new_row[key] = value
                if key == "tier":
                    new_row["split"] = "train"
                    inserted = True
            if not inserted:
                new_row["split"] = "train"
            out_lines.append(json.dumps(new_row, ensure_ascii=False))
            changed += 1

    if not check_only and changed:
        stories_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8", newline="\n")

    sha_after = sha256_of(stories_path) if (not check_only and changed) else sha_before
    return sha_before, sha_after, total, changed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify and report only; write nothing.")
    args = parser.parse_args(argv)

    print(f"{'file':<45} {'lines':>7} {'changed':>8}  sha256 before -> after")
    for stories_path, prompts_path in PAIRS:
        rel = stories_path.relative_to(ROOT)
        try:
            sha_before, sha_after, total, changed = migrate_file(stories_path, prompts_path, check_only=args.check)
        except (FileNotFoundError, ValueError) as exc:
            print(f"FAILED on {rel}: {exc}", file=sys.stderr)
            sys.exit(1)
        marker = "unchanged" if sha_before == sha_after else "MIGRATED"
        print(f"{str(rel):<45} {total:>7} {changed:>8}  {sha_before} -> {sha_after}  [{marker}]")


if __name__ == "__main__":
    main()
