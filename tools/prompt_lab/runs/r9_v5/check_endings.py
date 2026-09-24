"""Which stories do not end on sentence punctuation? (candidate truncation check)"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
END = re.compile(r"[.!?][\"'”’)]*$")
for f in [ROOT / "data/tier0/full/stories.jsonl", Path(__file__).parent / "baseline.jsonl", Path(__file__).parent / "v5.jsonl",
          Path(__file__).parent / "v5_dialogue_note.jsonl"]:
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    bad = [r for r in rows if not END.search(r["story"].strip())]
    print(f.name, len(rows), "no end punctuation:", len(bad))
    for r in bad:
        print("   ", r.get("prompt_hash", r.get("idx")), r.get("stop_reason", ""), repr(r["story"].strip()[-60:]))
