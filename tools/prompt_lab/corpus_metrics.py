"""Local quality metrics for a generated corpus (the numbers in data/tierN/README.md).

    python corpus_metrics.py --prompts data/tier0/train/prompts.jsonl --stories data/tier0/full/stories.jsonl [--cache <openrouter_cache>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from lifespan_learning.dataset_generation.response.openrouter_provider import story_defect  # noqa: E402

SENTENCE = re.compile(r"[^.!?]+[.!?]")


def read(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def used(word: str, story: str) -> bool:
    return re.search(r"\b" + re.escape(word.lower()), story.lower()) is not None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True)
    ap.add_argument("--stories", type=Path, required=True)
    ap.add_argument("--cache", type=Path)
    a = ap.parse_args()
    meta = {r["prompt_hash"]: r["metadata"] for r in read(a.prompts)}
    stories = read(a.stories)
    words = sents = paras = 0
    vocab = {"verb": 0, "noun": 0, "adjective": 0}
    defects, titles, because = [], 0, 0
    for s in stories:
        t = s["story"]
        words += len(t.split())
        sents += len(SENTENCE.findall(t))
        paras += len([p for p in t.split("\n") if p.strip()])
        m = meta[s["prompt_hash"]]
        for k in vocab:
            vocab[k] += used(m[k], t)
        if story_defect(t):
            defects.append((s["prompt_hash"][:8], story_defect(t)))
        titles += t.lstrip().startswith("#") or "**" in t
        because += len(re.findall(r"\bbecause\b", t, re.I))
    n = len(stories)
    print(f"stories: {n}/{len(meta)} prompts, empty: {sum(not s['story'].strip() for s in stories)}")
    print(f"mean words {words / n:.0f}, mean sentence length {words / max(1, sents):.1f} words, mean paragraphs {paras / n:.1f}")
    print("required vocabulary: " + ", ".join(f"{k} {v}/{n}" for k, v in vocab.items()) + f", total {sum(vocab.values())}/{3 * n} ({sum(vocab.values()) / (3 * n):.1%})")
    print(f"'because' per story {because / n:.2f}, titles/markdown {titles}, story_defect hits {len(defects)} {defects}")
    if a.cache and a.cache.exists():
        rows = [r for r in read(a.cache) if r.get("outcome") == "succeeded"]
        print(f"tokens: in {sum(r.get('in_tokens', 0) for r in rows):,} out {sum(r.get('out_tokens', 0) for r in rows):,}")


if __name__ == "__main__":
    main()
