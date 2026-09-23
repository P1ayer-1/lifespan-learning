"""Mix several runs' stories into shuffled blind files so a judge cannot tell
which generator wrote which story, then unmix the judgments.

    python mix_blind.py mix runs/r7_haiku runs/r7_glm --parts 2 --out runs/r7_mixed --seed 0
        -> runs/r7_mixed/partK.blind.jsonl, partK.targets.json, key.json
    python mix_blind.py unmix runs/r7_mixed
        -> writes <run>/baseline.judged.jsonl for every source run

Hidden ids are opaque ("s017"); key.json maps them back to (run, idx).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else HERE / q


def mix(runs: list[str], parts: int, out: str, seed: int) -> None:
    items = []
    for run in runs:
        rd = resolve(run)
        for line in (rd / "baseline.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                items.append({"run": run, "idx": r["idx"], "story": r["story"], "age": r["age"], "grade": r["grade"]})
    rng = random.Random(seed)
    rng.shuffle(items)
    out_dir = resolve(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = {}
    for k, it in enumerate(items):
        it["hid"] = f"s{k:03d}"
        key[it["hid"]] = {"run": it["run"], "idx": it["idx"]}
    (out_dir / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    for p in range(parts):
        chunk = items[p::parts]
        (out_dir / f"part{p}.blind.jsonl").write_text(
            "\n".join(json.dumps({"idx": it["hid"], "story": it["story"]}, ensure_ascii=False) for it in chunk) + "\n", encoding="utf-8")
        (out_dir / f"part{p}.targets.json").write_text(
            json.dumps({it["hid"]: {"age": it["age"], "grade": it["grade"]} for it in chunk}, indent=1), encoding="utf-8")
        print(f"part{p}: {len(chunk)} stories ({', '.join(f'{run}={sum(it['run'] == run for it in chunk)}' for run in runs)})")


def unmix(mixed: str) -> None:
    md = resolve(mixed)
    key = json.loads((md / "key.json").read_text(encoding="utf-8"))
    per_run: dict[str, list[dict]] = {}
    for jp in sorted(md.glob("part*.judged.jsonl")):
        for line in jp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                k = key[str(d["idx"])]
                per_run.setdefault(k["run"], []).append({"idx": k["idx"], "j": d["j"]})
    for run, rows in per_run.items():
        rows.sort(key=lambda r: r["idx"])
        (resolve(run) / "baseline.judged.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        print(f"{run}: {len(rows)} judgments")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mix"); m.add_argument("runs", nargs="+"); m.add_argument("--parts", type=int, default=2); m.add_argument("--out", required=True); m.add_argument("--seed", type=int, default=0)
    u = sub.add_parser("unmix"); u.add_argument("mixed")
    a = ap.parse_args()
    if a.cmd == "mix":
        mix(a.runs, a.parts, a.out, a.seed)
    else:
        unmix(a.mixed)
