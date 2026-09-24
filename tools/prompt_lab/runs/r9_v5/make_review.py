"""r9: local metrics for baseline vs v5, and blind fact/age review parts.

    python make_review.py export   -> review/fact_check/partK.jsonl, review/age_check/partK.jsonl, key.json, metrics.txt
    python make_review.py score    -> per-variant fail counts from the subagent outputs
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ["baseline", "v5"]
TAG = re.compile(r"</?\s*[a-zA-Z][^>]{0,20}>")


def read(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def field(prompt, pat):
    m = re.search(pat, prompt)
    return m.group(1).strip() if m else ""


def paragraphs(s):
    return [x for x in s.split("\n") if x.strip()]


def used(word, story):
    return re.search(r"\b" + re.escape(word.lower()), story.lower()) is not None


def export():
    rows = {v: read(HERE / f"{v}.jsonl") for v in VARIANTS}
    base_by_idx = {r["idx"]: r for r in rows["baseline"]}
    items, lines = [], []
    for v in VARIANTS:
        c = Counter()
        for r in rows[v]:
            bp = base_by_idx[r["idx"]]["prompt"]
            maxp = int(field(bp, r"Length: \d+-(\d+) paragraphs"))
            p = len(paragraphs(r["story"]))
            c["n"] += 1
            c["words"] += len(r["story"].split())
            c["over_max"] += p > maxp
            c["over_2x"] += p > 2 * maxp
            c["tags"] += bool(TAG.search(r["story"]))
            c["vocab"] += sum(used(r[k], r["story"]) for k in ("verb", "noun", "adjective"))
            c["because"] += len(re.findall(r"\bbecause\b", r["story"], re.I))
            oid = hashlib.sha256(f"r9|{v}|{r['idx']}".encode()).hexdigest()[:12]
            items.append({
                "id": oid, "variant": v, "idx": r["idx"], "story": r["story"],
                "fact": field(bp, r'real fact: "([^"]+)"'),
                "domain": field(bp, r"real-world idea about (.+?)\. "),
                "reading_level": field(bp, r"Reading level: (.+)"),
                "min_p": int(field(bp, r"Length: (\d+)-")), "max_p": maxp,
                "age": r["age"], "grade": r["grade"], "tone": field(bp, r"Tone: ([^:]+):"),
                "activity": field(bp, r"What happens: (.+)"),
                "words": {k: r[k] for k in ("verb", "noun", "adjective")},
            })
        n = c["n"]
        lines.append(f"{v}: n={n} mean_words={c['words'] / n:.0f} over_max_paragraphs={c['over_max']} over_2x={c['over_2x']} "
                     f"tag_artifacts={c['tags']} vocab_used={c['vocab']}/{3 * n} 'because'_per_story={c['because'] / n:.2f}")
    (HERE / "metrics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    random.Random(9).shuffle(items)
    (HERE / "key.json").write_text(json.dumps({i["id"]: i["variant"] for i in items}, indent=1), encoding="utf-8")
    fc, ac = HERE / "review" / "fact_check", HERE / "review" / "age_check"
    fc.mkdir(parents=True, exist_ok=True); ac.mkdir(parents=True, exist_ok=True)
    for k in range(0, len(items), 40):
        chunk = items[k:k + 40]
        (fc / f"part{k // 40}.jsonl").write_text("".join(json.dumps({
            "prompt_hash": i["id"], "phase": 0, "activity": i["activity"], "knowledge_domain": i["domain"],
            "fact": i["fact"], "story": i["story"]}, ensure_ascii=False) + "\n" for i in chunk), encoding="utf-8")
        (ac / f"part{k // 40}.jsonl").write_text("".join(json.dumps({
            "prompt_hash": i["id"], "phase": 0, "age": i["age"], "grade": i["grade"], "reading_level": i["reading_level"],
            "min_paragraphs": i["min_p"], "max_paragraphs": i["max_p"], "tone": i["tone"], "activity": i["activity"],
            "required_words": i["words"], "story": i["story"]}, ensure_ascii=False) + "\n" for i in chunk), encoding="utf-8")
    print(f"{len(items)} stories in {(len(items) + 39) // 40} parts per gate")


def score():
    key = json.loads((HERE / "key.json").read_text(encoding="utf-8"))
    out = []
    fc = Counter(); ac = Counter(); both = Counter(); hist = {v: Counter() for v in VARIANTS}
    fails = {v: {} for v in VARIANTS}
    for p in sorted((HERE / "review" / "fact_check").glob("part*.verdicts.jsonl")):
        for r in read(p):
            if r["verdict"] != "consistent":
                fc[key[r["prompt_hash"]]] += 1
                fails[key[r["prompt_hash"]]].setdefault(r["prompt_hash"], []).append(f"fact:{r['verdict']}: {r.get('reason', '')}")
    for p in sorted((HERE / "review" / "age_check").glob("part*.age.jsonl")):
        for r in read(p):
            v = key[r["prompt_hash"]]
            hist[v][r["score"]] += 1
            if r["score"] < 3:
                ac[v] += 1
                fails[v].setdefault(r["prompt_hash"], []).append(f"age:{r['score']}: {r.get('reason', '')}")
    for v in VARIANTS:
        out.append(f"{v}: fact_fail={fc[v]} age_fail={ac[v]} any_fail={len(fails[v])} age_scores={dict(sorted(hist[v].items()))}")
    (HERE / "score.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    (HERE / "fails.json").write_text(json.dumps(fails, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    {"export": export, "score": score}[sys.argv[1]]()
