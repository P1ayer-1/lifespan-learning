"""Candidate check for two stories glued together: "yard.Brielle" (no space after
sentence punctuation) and "TeddBlake" (a word cut off and the next story starting)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
NO_SPACE = re.compile(r"[a-z][.!?][\"'”’]?[A-Z]")
RUN_ON = re.compile(r"\b[A-Z]?[a-z]+[A-Z][a-z]+\b")
files = [ROOT / "data/tier0/full/stories.jsonl", ROOT / "data/_archive/tier0_2026-09-24_template_v2/full/stories.jsonl",
         Path(__file__).parent / "baseline.jsonl", Path(__file__).parent / "v5.jsonl", Path(__file__).parent / "v5_dialogue_note.jsonl"]
for f in files:
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{f.parent.name}/{f.name}: {len(rows)}")
    for r in rows:
        s = r["story"]
        for name, rx in (("no_space", NO_SPACE), ("run_on", RUN_ON)):
            for m in rx.finditer(s):
                print(f"   {name:8} {str(r.get('prompt_hash', r.get('idx')))[:8]} ...{s[max(0, m.start() - 25):m.end() + 15]!r}")
