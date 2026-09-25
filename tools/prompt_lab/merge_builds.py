"""Merge subagent-written builds into the files the repo reads.

Lexicons: lex_build/_gen/phase_{i}.json (one per phase, written by a subagent)
  -> sanitize (lowercase single words, stated-POS lists only), dedupe within a
     phase, then across phases so a word belongs to its EARLIEST phase
  -> lex_build/phase_{i}.json in the repo's lexicon format + summary.txt

Facts: facts/_gen/phase_{i}.json (generated) + facts/_verify/phase_{i}.json
  (verdicts written by an independent subagent: [{"i": idx, "verdict": ..., "reason": ...}])
  -> facts/phase_{i}.json keeping only verdict == "true", in the format
     engine/facts.py reads, + summary.txt. Without a verify file the phase is
     skipped (unverified facts never ship).

Activity facts: facts/activity/_gen/part{k}.json + facts/activity/_verify/part{k}.json
  (same verdict format, see facts/activity/SPEC.md) -> keep verdict == "true",
  and add them, each tagged with its content_key, to facts/phase_0.json next to
  the domain facts already there (earlier activity facts are replaced). Warns
  about any activity in facts/activity/phase_0_activities.json left with fewer
  than MIN_ACTIVITY_FACTS facts. facts/activity/revisions.json then retires
  facts that failed corpus review and swaps in rewordings that
  facts/activity/_verify/revisions.json marks true.

Usage:
    python merge_builds.py lexicons
    python merge_builds.py facts
    python merge_builds.py activity-facts
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORD_RE = re.compile(r"[a-z][a-z-]{1,20}")
POS = ("verbs", "nouns", "adjectives")


def merge_lexicons() -> None:
    gen_dir, out_dir = HERE / "lex_build" / "_gen", HERE / "lex_build"
    seen: dict[str, set[str]] = {p: set() for p in POS}
    lines = []
    for ph in range(7):
        src = gen_dir / f"phase_{ph}.json"
        if not src.exists():
            lines.append(f"phase {ph}: MISSING {src}")
            continue
        raw = json.loads(src.read_text(encoding="utf-8"))
        final = {}
        dropped = Counter()
        for p in POS:
            words = []
            for w in raw.get(p, []):
                w = str(w).strip().lower()
                if not WORD_RE.fullmatch(w):
                    dropped["malformed"] += 1
                    continue
                if w in seen[p]:
                    dropped["earlier_phase"] += 1
                    continue
                if w in words:
                    dropped["duplicate"] += 1
                    continue
                words.append(w)
            seen[p].update(words)
            final[p] = sorted(words)
        (out_dir / f"phase_{ph}.json").write_text(json.dumps(final, indent=1), encoding="utf-8")
        lines.append(f"phase {ph}: " + ", ".join(f"{p}={len(final[p])}" for p in POS)
                     + f" | dropped {dict(dropped)} | e.g. " + ", ".join(final["nouns"][:6]))
    (out_dir / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def merge_facts() -> None:
    gen_dir, ver_dir, out_dir = HERE / "facts" / "_gen", HERE / "facts" / "_verify", HERE / "facts"
    lines = []
    for ph in range(7):
        g, v = gen_dir / f"phase_{ph}.json", ver_dir / f"phase_{ph}.json"
        if not g.exists() or not v.exists():
            lines.append(f"phase {ph}: missing {'generated' if not g.exists() else 'verify'} file; skipped")
            continue
        data = json.loads(g.read_text(encoding="utf-8"))
        facts = data["facts"]
        verdicts = {int(x["i"]): x for x in json.loads(v.read_text(encoding="utf-8"))}
        keep, counts = [], Counter()
        for i, f in enumerate(facts):
            verdict = verdicts.get(i, {"verdict": "unverified"})["verdict"]
            counts[verdict] += 1
            if verdict == "true" and f.get("fact") and f.get("domain"):
                keep.append({"domain": f["domain"], "fact": f["fact"].strip(), "hook": f.get("hook", "").strip()})
        (out_dir / f"phase_{ph}.json").write_text(
            json.dumps({"phase": ph, "band": data.get("band", ""), "generated_by": data.get("generated_by", "subagent"),
                        "verified_by": "independent subagent", "facts": keep}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        per_domain = Counter(f["domain"] for f in keep)
        lines.append(f"phase {ph}: {len(facts)} generated, kept {len(keep)}; verdicts {dict(counts)}; per domain {dict(per_domain)}")
    (out_dir / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


MIN_ACTIVITY_FACTS = 6


def _apply_revisions(keep: list[dict], act_dir: Path, lines: list[str]) -> list[dict]:
    """Retire and reword verified facts per facts/activity/revisions.json.

    A reword replaces its "from" fact only when _verify/revisions.json marks it
    true; otherwise the old fact is dropped, since it was revised for failing.
    Entries that match no kept fact are reported, not ignored silently.
    """
    src = act_dir / "revisions.json"
    if not src.exists():
        return keep
    rev = json.loads(src.read_text(encoding="utf-8"))
    ver_path = act_dir / "_verify" / "revisions.json"
    verdicts = {int(x["i"]): x["verdict"] for x in json.loads(ver_path.read_text(encoding="utf-8"))} if ver_path.exists() else {}
    retire = {(r["content_key"], r["fact"]) for r in rev.get("retire", [])}
    reword = {(r["content_key"], r["from"]): (i, r) for i, r in enumerate(rev.get("reword", []))}
    out, hit, counts = [], set(), Counter()
    for f in keep:
        key = (f["content_key"], f["fact"])
        if key in retire:
            hit.add(key)
            counts["retired"] += 1
        elif key in reword:
            hit.add(key)
            i, r = reword[key]
            if verdicts.get(i) == "true":
                out.append({"content_key": r["content_key"], "fact": r["fact"].strip(), "hook": r.get("hook", "").strip()})
                counts["reworded"] += 1
            else:
                counts["reword_unverified_dropped"] += 1
        else:
            out.append(f)
    missing = (retire | set(reword)) - hit
    lines.append(f"revisions: {dict(counts)}" + (f"; not found: {sorted(missing)}" if missing else ""))
    return out


def merge_activity_facts() -> None:
    act_dir, out = HERE / "facts" / "activity", HERE / "facts" / "phase_0.json"
    activities = [a["content_key"] for a in json.loads((act_dir / "phase_0_activities.json").read_text(encoding="utf-8"))["activities"]]
    keep, counts, lines = [], Counter(), []
    for g in sorted((act_dir / "_gen").glob("part*.json")):
        v = act_dir / "_verify" / g.name
        if not v.exists():
            lines.append(f"{g.name}: no verify file; skipped")
            continue
        facts = json.loads(g.read_text(encoding="utf-8"))["facts"]
        verdicts = {int(x["i"]): x["verdict"] for x in json.loads(v.read_text(encoding="utf-8"))}
        part_counts = Counter(verdicts.get(i, "unverified") for i in range(len(facts)))
        counts.update(part_counts)
        lines.append(f"{g.name}: {len(facts)} generated, verdicts {dict(part_counts)}")
        keep += [{"content_key": f["content_key"], "fact": f["fact"].strip(), "hook": f.get("hook", "").strip()}
                 for i, f in enumerate(facts) if verdicts.get(i) == "true" and f.get("fact") and f.get("content_key") in activities]
    keep = _apply_revisions(keep, act_dir, lines)
    bank = json.loads(out.read_text(encoding="utf-8"))
    bank["facts"] = [f for f in bank["facts"] if not f.get("content_key")] + keep
    out.write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8")
    per_key = Counter(f["content_key"] for f in keep)
    thin = {k: per_key.get(k, 0) for k in activities if per_key.get(k, 0) < MIN_ACTIVITY_FACTS}
    lines.append(f"kept {len(keep)} activity facts for {len(per_key)}/{len(activities)} activities; verdicts {dict(counts)}")
    lines.append(f"activities under {MIN_ACTIVITY_FACTS} facts: {thin or 'none'}")
    (act_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    {"lexicons": merge_lexicons, "facts": merge_facts, "activity-facts": merge_activity_facts}[sys.argv[1]]()
