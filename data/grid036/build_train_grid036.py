"""Build the grid036 training directory from the reviewed corpus.

Drops, per docs/DECISIONS.md (2026-10-01, audit outcome + full fact check):
  * every story whose fact verdict is not "consistent" (audit sample, all phases;
    full fact check, phases 3 and 6),
  * every audited story with age score < 3,
  * mechanical defects: CJK characters, "continue reading", a repeated paragraph.
Phases 3 and 6 must have a fact verdict for every story or the build refuses.
No regeneration. Prints counts and hashes only -- never story text.

Run from D:\\Lifespan\\Lifespan with PYTHONPATH set to it.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

CL = Path(r"D:\Lifespan\curriculum-learning\data\grid036")
OUT = Path(r"D:\Lifespan\grid036_train")
REPORT = Path(r"D:\Lifespan\exams_grid036\scratch\build_train_report.json")
EXPERIMENT_ID = "lifespan-grid036"
PHASES = (0, 3, 6)
FULL_FACT = (3, 6)
REPLAY_SEED = 4243
REPLAY_PER_PHASE = 500
AGE_PASS = 3
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def fail(msg: str) -> None:
    print("REFUSED: " + msg)
    sys.exit(2)


def rows(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()]


def verdict_map(d: Path, suffix: str, field: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for part in sorted(d.glob("part*.jsonl")):
        if part.name.endswith(suffix) or part.name.count(".") > 1:
            continue
        vp = part.with_name(part.name[: -len(".jsonl")] + suffix)
        if not vp.exists():
            fail(f"missing {vp}")
        ph = [r["prompt_hash"] for r in rows(part)]
        vr = rows(vp)
        if ph != [r["prompt_hash"] for r in vr]:
            fail(f"hash order mismatch {vp}")
        for r in vr:
            out[r["prompt_hash"]] = r[field]
    return out


def mechanical(story: str) -> bool:
    paras = [p.strip() for p in story.split("\n\n") if p.strip()]
    return bool(CJK.search(story)) or "continue reading" in story.lower() or len(paras) != len(set(paras))


if OUT.exists():
    fail(f"{OUT} exists; build once")
R: dict = {"experiment_id": EXPERIMENT_ID, "phases": {}}
kept: dict[int, list[str]] = {}
kept_hashes: dict[int, list[str]] = {}
models = set()
for k in PHASES:
    src = CL / f"phase{k}/train/stories.jsonl"
    lines = [l for l in src.read_bytes().decode("utf-8").split("\n") if l.strip()]
    fact = verdict_map(CL / f"phase{k}/audit/fact_check", ".verdicts.jsonl", "verdict")
    age = verdict_map(CL / f"phase{k}/audit/age_check", ".age.jsonl", "score")
    if k in FULL_FACT:
        ff = verdict_map(CL / f"phase{k}/fullfact/fact_check", ".verdicts.jsonl", "verdict")
        if set(ff) & set(fact):
            fail(f"phase {k}: full-fact and audit overlap")
        fact.update(ff)
    c = Counter()
    kept[k], kept_hashes[k] = [], []
    seen = set()
    for l in lines:
        r = json.loads(l)
        h = r["prompt_hash"]
        if r.get("split") != "train" or int(r["phase"]) != k:
            fail(f"phase {k}: row {h[:12]} split/phase wrong")
        if h in seen:
            fail(f"phase {k}: duplicate prompt_hash {h[:12]}")
        seen.add(h)
        models.add(r["model"])
        if k in FULL_FACT and h not in fact:
            fail(f"phase {k}: {h[:12]} has no fact verdict")
        reasons = []
        if h in fact and fact[h] != "consistent":
            reasons.append(f"fact_{fact[h]}")
        if h in age and int(age[h]) < AGE_PASS:
            reasons.append("age")
        if mechanical(r["story"]):
            reasons.append("mechanical")
        for x in reasons:
            c[x] += 1
        if reasons:
            c["dropped"] += 1
            continue
        kept[k].append(l)
        kept_hashes[k].append(h)
    if set(fact) - seen or set(age) - seen:
        fail(f"phase {k}: verdicts for hashes not in the corpus")
    c["source"] = len(lines)
    c["kept"] = len(kept[k])
    c["fact_reviewed"] = len(fact)
    c["age_reviewed"] = len(age)
    R["phases"][k] = dict(sorted(c.items()))
if len(models) != 1:
    fail(f"generator models {models}")

(OUT / "replay").mkdir(parents=True)
R["files"] = {}
for k in PHASES:
    dst = OUT / f"train_phase_{k}.jsonl"
    dst.write_bytes(("\n".join(kept[k]) + "\n").encode("utf-8"))
    R["files"][dst.name] = {"lines": len(kept[k]), "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
    key = f"{EXPERIMENT_ID}|replay|phase{k}|{REPLAY_SEED}".encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))
    chosen = sorted(rng.sample(sorted(kept_hashes[k]), REPLAY_PER_PHASE))
    rp = OUT / "replay" / f"phase_{k}.json"
    rp.write_bytes((json.dumps({"seed": REPLAY_SEED, "prompt_hashes": chosen}) + "\n").encode("utf-8"))
    R["files"][f"replay/phase_{k}.json"] = {"n": len(chosen), "sha256": hashlib.sha256(rp.read_bytes()).hexdigest()}
R["generator_model"] = next(iter(models))
R["replay_selection"] = (
    f"random.Random(int(sha256('{EXPERIMENT_ID}|replay|phase{{k}}|{REPLAY_SEED}')[:8 bytes]))"
    f".sample(sorted kept prompt_hashes, {REPLAY_PER_PHASE}), then sorted"
)
out = json.dumps(R, indent=1, sort_keys=True)
REPORT.write_bytes((out + "\n").encode("utf-8"))
print(out)
