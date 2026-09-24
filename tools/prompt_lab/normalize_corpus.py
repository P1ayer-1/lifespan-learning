"""Join production prompt/story files into prompt_lab's blind-judge format.

The production writer intentionally keeps prompts, stories, and provider usage
separate. This adapter creates the compact ``baseline.jsonl`` consumed by
``judge.py`` while preserving prompt order and reporting observed token use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--stories", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    prompts = read_jsonl(args.prompts)
    stories = {row["prompt_hash"]: row for row in read_jsonl(args.stories)}
    usage = {
        row["custom_id"]: row
        for row in read_jsonl(args.cache)
        if row.get("outcome") == "succeeded"
    }

    missing = [row["prompt_hash"] for row in prompts if row["prompt_hash"] not in stories]
    if missing:
        raise SystemExit(f"missing {len(missing)} stories; first hash: {missing[0]}")

    output = []
    for idx, prompt in enumerate(prompts):
        prompt_hash = prompt["prompt_hash"]
        metadata = prompt["metadata"]
        story = stories[prompt_hash]
        token_usage = usage.get(prompt_hash, {})
        output.append({
            "variant": "baseline",
            "idx": idx,
            "phase": metadata["phase"],
            "tier": metadata["tier"],
            "age": metadata["age"],
            "grade": metadata["grade"],
            "verb": metadata["verb"],
            "noun": metadata["noun"],
            "adjective": metadata["adjective"],
            "story": story["story"],
            "stop_reason": "stop",
            "model": story["model"],
            "in_tokens": token_usage.get("in_tokens"),
            "out_tokens": token_usage.get("out_tokens"),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in output) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote={len(output)} input_tokens={sum(row['in_tokens'] or 0 for row in output)} "
        f"output_tokens={sum(row['out_tokens'] or 0 for row in output)}"
    )


if __name__ == "__main__":
    main()
