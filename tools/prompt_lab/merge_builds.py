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

Usage:
    python merge_builds.py lexicons
    python merge_builds.py facts
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


if __name__ == "__main__":
    {"lexicons": merge_lexicons, "facts": merge_facts}[sys.argv[1]]()
