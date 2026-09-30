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
  for phase 0 (facts/activity/_gen{N}/part{k}.json + _verify{N}/part{k}.json for
  phase N != 0, e.g. _gen3/_verify3 for phase 3, _gen6/_verify6 for phase 6 --
  see facts/activity/SPEC_phase3_6.md) (same verdict format, see
  facts/activity/SPEC.md) -> keep verdict == "true", and add them, each tagged
  with its content_key, to facts/phase_{N}.json next to the domain facts
  already there (earlier activity facts for that phase are replaced; domain
  facts are untouched). Warns about any activity in
  facts/activity/phase_{N}_activities.json left with fewer than
  MIN_ACTIVITY_FACTS facts. facts/activity/revisions.json (revisions{N}.json
  for phase N != 0) then retires facts that failed corpus review and swaps in
  rewordings that the matching file under facts/activity/_verify/ marks true.

Usage:
    python merge_builds.py lexicons
    python merge_builds.py facts
    python merge_builds.py activity-facts [phase]   # phase defaults to 0
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


def _tag_row_activity(facts: list[dict], assign_path: Path) -> None:
    """Tag each fact with the activity text of the row it was written for.

    Phases 3 and 6 split one content_key into several rows with different
    goals (e.g. learning_math: fractions, congruent triangles). Keyed on
    content_key alone, a fractions prompt could be handed a triangle fact
    (2026-09-30 review: 380/1000 phase-3 prompts). The writer's assign file
    lists the part's rows in order, each with an equal block of facts.
    Parts without an assign file (phase 0) are left untagged.
    """
    if not assign_path.exists():
        return
    rows = json.loads(assign_path.read_text(encoding="utf-8"))["activities"]
    per, rem = divmod(len(facts), len(rows))
    if rem or not per:
        raise ValueError(f"{assign_path.name}: {len(facts)} facts do not split evenly over {len(rows)} rows")
    for i, f in enumerate(facts):
        row = rows[i // per]
        if f.get("content_key") != row["content_key"]:
            raise ValueError(f"{assign_path.name}: fact {i} is {f.get('content_key')!r}, row is {row['content_key']!r}")
        f["activity"] = row["activity"]


def _apply_revisions(keep: list[dict], act_dir: Path, lines: list[str],
                      revisions_name: str = "revisions.json") -> list[dict]:
    """Retire and reword verified facts per facts/activity/<revisions_name>.

    A reword replaces its "from" fact only when the matching verify file marks
    it true; otherwise the old fact is dropped, since it was revised for
    failing. Entries that match no kept fact are reported, not ignored
    silently.
    """
    src = act_dir / revisions_name
    if not src.exists():
        return keep
    rev = json.loads(src.read_text(encoding="utf-8"))
    ver_path = act_dir / "_verify" / revisions_name
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
                out.append({"content_key": r["content_key"], "fact": r["fact"].strip(), "hook": r.get("hook", "").strip(),
                            **({"activity": f["activity"]} if "activity" in f else {})})
                counts["reworded"] += 1
            else:
                counts["reword_unverified_dropped"] += 1
        else:
            out.append(f)
    missing = (retire | set(reword)) - hit
    lines.append(f"revisions: {dict(counts)}" + (f"; not found: {sorted(missing)}" if missing else ""))
    return out


def merge_activity_facts(phase: int = 0, base_dir: Path | None = None) -> None:
    """Merge one phase's per-activity builds into facts/phase_{phase}.json.

    Phase 0 keeps its original directory names (_gen, _verify, revisions.json)
    for backward compatibility; phase N != 0 reads facts/activity/_gen{N} and
    _verify{N} (per the phase_3/phase_6 fact-bank build,
    facts/activity/SPEC_phase3_6.md) against facts/activity/phase_{N}_activities.json,
    and (if present) a phase-specific facts/activity/revisions{N}.json.
    `base_dir` overrides `HERE / "facts"` for tests; production callers leave
    it unset.
    """
    facts_dir = base_dir or (HERE / "facts")
    act_dir, out = facts_dir / "activity", facts_dir / f"phase_{phase}.json"
    gen_dir = act_dir / ("_gen" if phase == 0 else f"_gen{phase}")
    verify_dir = act_dir / ("_verify" if phase == 0 else f"_verify{phase}")
    revisions_name = "revisions.json" if phase == 0 else f"revisions{phase}.json"
    activities_path = act_dir / f"phase_{phase}_activities.json"
    activities = [a["content_key"] for a in json.loads(activities_path.read_text(encoding="utf-8"))["activities"]]
    keep, counts, lines = [], Counter(), []
    for g in sorted(gen_dir.glob("part*.json")):
        v = verify_dir / g.name
        if not v.exists():
            lines.append(f"{g.name}: no verify file; skipped")
            continue
        facts = json.loads(g.read_text(encoding="utf-8"))["facts"]
        _tag_row_activity(facts, gen_dir / f"assign_{g.name}")
        verdicts = {int(x["i"]): x["verdict"] for x in json.loads(v.read_text(encoding="utf-8"))}
        part_counts = Counter(verdicts.get(i, "unverified") for i in range(len(facts)))
        counts.update(part_counts)
        lines.append(f"{g.name}: {len(facts)} generated, verdicts {dict(part_counts)}")
        keep += [{"content_key": f["content_key"], "fact": f["fact"].strip(), "hook": f.get("hook", "").strip(),
                  **({"activity": f["activity"]} if "activity" in f else {})}
                 for i, f in enumerate(facts) if verdicts.get(i) == "true" and f.get("fact") and f.get("content_key") in activities]
    keep = _apply_revisions(keep, act_dir, lines, revisions_name)
    bank = json.loads(out.read_text(encoding="utf-8"))
    bank["facts"] = [f for f in bank["facts"] if not f.get("content_key")] + keep
    out.write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    per_key = Counter(f["content_key"] for f in keep)
    thin = {k: per_key.get(k, 0) for k in activities if per_key.get(k, 0) < MIN_ACTIVITY_FACTS}
    lines.append(f"kept {len(keep)} activity facts for {len(per_key)}/{len(set(activities))} activities; verdicts {dict(counts)}")
    lines.append(f"activities under {MIN_ACTIVITY_FACTS} facts: {thin or 'none'}")
    (act_dir / f"summary{'' if phase == 0 else phase}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if sys.argv[1] == "activity-facts":
        merge_activity_facts(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    else:
        {"lexicons": merge_lexicons, "facts": merge_facts}[sys.argv[1]]()
