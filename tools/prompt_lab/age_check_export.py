"""Post-generation age-fit gate, subagent-driven (no API spend).

The subagent counterpart of ``lifespan_learning.dataset_generation.quality.
age_check_gate``: same five levels, same pass threshold, same per-story output
row, but the scores come from a subagent reading exported parts instead of
Haiku calls.

    python age_check_export.py export --prompts train/prompts.jsonl --stories full/stories.jsonl --out quality/age_check --chunk 40
        -> quality/age_check/partK.jsonl  (story plus target age, grade, reading-level instruction,
           paragraph bounds, tone and required words, one per line)
    (a subagent reads each part and writes quality/age_check/partK.age.jsonl:
        {"prompt_hash": ..., "score": 0-4, "reason": "..."})
    python age_check_export.py apply --stories full/stories.jsonl --dir quality/age_check
        -> quality/age_check/age_check.jsonl (age_check_gate's row format plus reason),
           full/stories.jsonl.age_regen_queue.jsonl (failing hashes), quality/age_check/report.txt

The queue name differs from fact_check_export's ``.regen_queue.jsonl`` so the
two gates never overwrite each other.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from lifespan_learning.dataset_generation.quality.age_check_gate import LEVELS, PASS_THRESHOLD

REVIEWER = "subagent:story-age-fit-reviewer"


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def export(prompts: Path, stories: Path, out: Path, chunk: int) -> None:
    meta = {r["prompt_hash"]: r["metadata"] for r in read_jsonl(prompts)}
    rows = []
    for s in read_jsonl(stories):
        m = meta.get(s["prompt_hash"])
        if m is None:
            continue  # no prompt for this story; the gate cannot know its target age
        rows.append({
            "prompt_hash": s["prompt_hash"],
            "phase": m.get("phase", s.get("phase")),
            "age": m["age"],
            "grade": m.get("grade", ""),
            "reading_level": m.get("reading_level", ""),
            "min_paragraphs": m.get("min_paragraphs"),
            "max_paragraphs": m.get("max_paragraphs"),
            "tone": m.get("tone", ""),
            "activity": m.get("goal", ""),
            "required_words": {k: m.get(k, "") for k in ("verb", "noun", "adjective")},
            "story": s["story"],
        })
    out.mkdir(parents=True, exist_ok=True)
    for k, i in enumerate(range(0, len(rows), chunk)):
        (out / f"part{k}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows[i:i + chunk]) + "\n", encoding="utf-8")
    print(f"exported {len(rows)} stories in {(len(rows) + chunk - 1) // chunk} parts to {out}")


def apply(stories: Path, d: Path, pass_threshold: int = PASS_THRESHOLD) -> None:
    ages = {}
    for pp in sorted(d.glob("part*.jsonl")):
        if pp.name.endswith(".age.jsonl"):
            continue
        for r in read_jsonl(pp):
            ages[r["prompt_hash"]] = r["age"]
    scores: dict[str, dict] = {}
    for vp in sorted(d.glob("part*.age.jsonl")):
        for v in read_jsonl(vp):
            if v["score"] not in range(len(LEVELS)):
                raise ValueError(f"{vp.name}: score {v['score']!r} for {v['prompt_hash']} is not 0-{len(LEVELS) - 1}")
            scores[v["prompt_hash"]] = v
    rows = read_jsonl(stories)
    results, failing, missing = [], [], 0
    per_phase: dict[int, Counter] = {}
    for r in rows:
        v = scores.get(r["prompt_hash"])
        if v is None:
            missing += 1
            continue
        passed = v["score"] >= pass_threshold
        results.append({
            "prompt_hash": r["prompt_hash"], "phase": r["phase"], "age": ages.get(r["prompt_hash"]),
            "score": v["score"], "passed": passed, "model": REVIEWER, "reason": v.get("reason", ""),
        })
        per_phase.setdefault(r["phase"], Counter())[v["score"]] += 1
        if not passed:
            failing.append({"prompt_hash": r["prompt_hash"], "phase": r["phase"], "score": v["score"], "reason": v.get("reason", "")})
    (d / "age_check.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in results), encoding="utf-8")
    queue = stories.with_suffix(stories.suffix + ".age_regen_queue.jsonl")
    queue.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in failing), encoding="utf-8")
    lines = [f"{len(rows)} stories, {len(results)} scored, {missing} unscored, {len(failing)} queued for regeneration -> {queue.name}"]
    for ph in sorted(per_phase):
        c = per_phase[ph]
        total = sum(c.values())
        passed = sum(n for s, n in c.items() if s >= pass_threshold)
        lines.append(f"phase {ph}: pass {passed}/{total} " + ", ".join(f"score{s}={c[s]}" for s in range(len(LEVELS))))
    (d / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--prompts", type=Path, required=True); e.add_argument("--stories", type=Path, required=True); e.add_argument("--out", type=Path, required=True); e.add_argument("--chunk", type=int, default=40)
    a = sub.add_parser("apply"); a.add_argument("--stories", type=Path, required=True); a.add_argument("--dir", type=Path, required=True); a.add_argument("--pass-threshold", type=int, default=PASS_THRESHOLD)
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.prompts, args.stories, args.out, args.chunk)
    else:
        apply(args.stories, args.dir, args.pass_threshold)
