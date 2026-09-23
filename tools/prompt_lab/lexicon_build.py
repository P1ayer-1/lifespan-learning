"""Build graded lexicons (verbs / nouns / adjectives) per phase with Claude Sonnet 5.

Why: the audit of the existing lexicons (lex_audit/report.txt) shows the
phase 3-6 lists, extracted from 19th-century novels, are mostly band 0-2
words ('say', 'go', 'time'), with POS errors ('lightning' as a verb) and
archaic or offensive entries. A phase lexicon should hold words a reader
typically FIRST learns in that band, so the cloze exam and the 'use these
words' instruction actually distinguish phases.

Each phase is requested in several topical slices for coverage (one call
per slice returns all three parts of speech), then words are deduplicated
across phases: a word that appears in more than one phase is kept only in
the earliest. Every API answer is cached under _cache/ so a killed run
resumes. Output: lex_build/phase_{i}.json in the repo's lexicon format.

Usage:
    python lexicon_build.py --per-slice 40 --out lex_build
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from gen_ab import load_env

MODEL = "claude-sonnet-5"
BANDS = ["junior/senior kindergarten (age 3-5)", "grades 1-2 (age 6-8)", "grades 3-5 (age 8-11)", "grades 6-8 (age 11-14)",
         "grades 9-10 (age 14-16)", "grade 11 (age 16-17)", "grade 12 (age 17-18)"]
POS_DESC = {
    "verbs": "verbs (base form, e.g. 'measure', 'persuade')",
    "nouns": "nouns (singular, concrete or abstract, e.g. 'shadow', 'evidence'; no proper nouns)",
    "adjectives": "adjectives (e.g. 'sticky', 'reluctant'; no nationalities, no numbers)",
}
SLICES = ["home, family and daily life", "school, learning and play", "nature, animals and weather", "the body, feelings and health",
          "things, tools, machines and materials", "people, society and work", "ideas, thinking and talking"]

TOOL = {
    "name": "record_words",
    "description": "Record the three word lists.",
    "strict": True,
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["verbs", "nouns", "adjectives"],
        "properties": {pos: {"type": "array", "items": {"type": "string"}} for pos in ("verbs", "nouns", "adjectives")},
    },
}
WORD_RE = re.compile(r"[a-z][a-z-]{1,20}")


def ask(client, phase: int, slice_: str, n: int) -> dict[str, list[str]]:
    import anthropic
    earlier = f" A reader in {BANDS[phase - 1]} would typically NOT yet know or use these words comfortably." if phase > 0 else ""
    pos_lines = "\n".join(f"- {n} {POS_DESC[pos]}" for pos in POS_DESC)
    prompt = (
        f"For a graded reading curriculum, list English words that a typical reader FIRST learns in {BANDS[phase]}, drawn from the "
        f"topic area '{slice_}'.{earlier} Choose words that reading-level research (Tier 1/Tier 2 vocabulary, grade-level word lists) "
        f"places at this band: known and usable by most readers at the END of this band, but new to most readers entering it. Give:\n"
        f"{pos_lines}\n"
        f"Single words only, lowercase, modern everyday North American English, no slang, no archaic words, nothing violent or adult, "
        f"no proper nouns. Record them with record_words."
    )
    for attempt in range(6):
        try:
            r = client.messages.create(model=MODEL, max_tokens=4000, thinking={"type": "adaptive"}, output_config={"effort": "medium"},
                                       tools=[TOOL], tool_choice={"type": "auto"}, messages=[{"role": "user", "content": prompt}])
            for b in r.content:
                if b.type == "tool_use":
                    return {pos: [w.strip().lower() for w in b.input[pos] if WORD_RE.fullmatch(w.strip().lower())] for pos in POS_DESC}
            return {pos: [] for pos in POS_DESC}
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            time.sleep(min(30, 2 ** attempt))
    return {pos: [] for pos in POS_DESC}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-slice", type=int, default=40)
    ap.add_argument("--out", type=Path, default=Path("lex_build"))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    load_env()
    out_dir = args.out if args.out.is_absolute() else Path(__file__).resolve().parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "_cache"
    cache_dir.mkdir(exist_ok=True)
    import anthropic
    client = anthropic.Anthropic()

    def ask_cached(ph, si, s):
        p = cache_dir / f"{ph}_{si}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        got = ask(client, ph, s, args.per_slice)
        p.write_text(json.dumps(got), encoding="utf-8")
        return got

    raw: dict[tuple[int, str], list[str]] = {}
    jobs = [(ph, si, s) for ph in range(7) for si, s in enumerate(SLICES)]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(ask_cached, ph, si, s): ph for ph, si, s in jobs}
        for n, fut in enumerate(as_completed(futs), 1):
            ph = futs[fut]
            got = fut.result()
            for pos in POS_DESC:
                raw.setdefault((ph, pos), []).extend(got[pos])
            if n % 7 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)

    # dedupe within phase, then across phases (earliest phase wins), per POS
    seen: dict[str, set[str]] = {pos: set() for pos in POS_DESC}
    final: dict[int, dict[str, list[str]]] = {}
    for ph in range(7):
        final[ph] = {}
        for pos in POS_DESC:
            words = []
            for w in raw.get((ph, pos), []):
                if w not in seen[pos] and w not in words:
                    words.append(w)
            seen[pos].update(words)
            final[ph][pos] = sorted(words)
        (out_dir / f"phase_{ph}.json").write_text(json.dumps(final[ph], indent=1), encoding="utf-8")
    lines = []
    for ph in range(7):
        lines.append(f"phase {ph}: " + ", ".join(f"{pos}={len(final[ph][pos])}" for pos in POS_DESC)
                     + " | e.g. " + ", ".join(final[ph]["nouns"][:8]))
    print("\n".join(lines))
    (out_dir / "summary.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
