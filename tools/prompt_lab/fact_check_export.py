"""Fact-consistency gate, subagent-driven (no API spend).

Every prompt carries the verified fact its story must turn on (prompt
metadata "fact"). This tool pairs each generated story with that fact and
exports review files for a subagent checker; the checker writes one verdict
per story; `apply` turns failing stories into a regeneration queue in the
same shape generate_responses.py already uses (<out>.regen_queue.jsonl),
and writes a per-phase report.

    python fact_check_export.py export --prompts train_prompts.jsonl --stories train_stories.jsonl --out fc/train --chunk 40
        -> fc/train/partK.jsonl  ({"prompt_hash", "phase", "fact", "story"} per line)
    (a subagent reads each part and writes fc/train/partK.verdicts.jsonl:
        {"prompt_hash": ..., "verdict": "consistent" | "contradicts_fact" | "adds_false_claim" | "fact_missing", "reason": "..."})
    python fact_check_export.py apply --stories train_stories.jsonl --dir fc/train
        -> train_stories.jsonl.regen_queue.jsonl (failing hashes), fc/train/report.txt

Verdicts: "consistent" passes. "contradicts_fact" (the story states the
fact wrongly), "adds_false_claim" (the story adds a false mechanism, number
or claim of its own) and "fact_missing" (the story never uses the fact)
fail and are queued for regeneration.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

FAIL = {"contradicts_fact", "adds_false_claim", "fact_missing"}


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def export(prompts: Path, stories: Path, out: Path, chunk: int) -> None:
    facts = {r["prompt_hash"]: (r["metadata"].get("fact", ""), r["metadata"].get("phase")) for r in read_jsonl(prompts)}
    rows = []
    for s in read_jsonl(stories):
        fact, phase = facts.get(s["prompt_hash"], ("", s.get("phase")))
        rows.append({"prompt_hash": s["prompt_hash"], "phase": phase, "fact": fact, "story": s["story"]})
    out.mkdir(parents=True, exist_ok=True)
    for k, i in enumerate(range(0, len(rows), chunk)):
        (out / f"part{k}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows[i:i + chunk]) + "\n", encoding="utf-8")
    print(f"exported {len(rows)} stories in {(len(rows) + chunk - 1) // chunk} parts to {out}")


def apply(stories: Path, d: Path) -> None:
    verdicts: dict[str, dict] = {}
    for vp in sorted(d.glob("part*.verdicts.jsonl")):
        for v in read_jsonl(vp):
            verdicts[v["prompt_hash"]] = v
    rows = read_jsonl(stories)
    missing = [r["prompt_hash"] for r in rows if r["prompt_hash"] not in verdicts]
    per_phase: dict[int, Counter] = {}
    failing = []
    for r in rows:
        v = verdicts.get(r["prompt_hash"])
        if v is None:
            continue
        per_phase.setdefault(r["phase"], Counter())[v["verdict"]] += 1
        if v["verdict"] in FAIL:
            failing.append({"prompt_hash": r["prompt_hash"], "phase": r["phase"], "verdict": v["verdict"], "reason": v.get("reason", "")})
    queue = stories.with_suffix(stories.suffix + ".regen_queue.jsonl")
    queue.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in failing) + ("\n" if failing else ""), encoding="utf-8")
    lines = [f"{len(rows)} stories, {len(verdicts)} verdicts, {len(missing)} unverified, {len(failing)} queued for regeneration -> {queue.name}"]
    for ph in sorted(per_phase):
        c = per_phase[ph]
        total = sum(c.values())
        lines.append(f"phase {ph}: pass {c.get('consistent', 0)}/{total} " + ", ".join(f"{k}={n}" for k, n in sorted(c.items()) if k != "consistent"))
    (d / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--prompts", type=Path, required=True); e.add_argument("--stories", type=Path, required=True); e.add_argument("--out", type=Path, required=True); e.add_argument("--chunk", type=int, default=40)
    a = sub.add_parser("apply"); a.add_argument("--stories", type=Path, required=True); a.add_argument("--dir", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.prompts, args.stories, args.out, args.chunk)
    else:
        apply(args.stories, args.dir)
