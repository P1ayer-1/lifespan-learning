"""Audit the seven phase lexicons with the generation model.

For every word, in batches, ask Claude Haiku 4.5 (strict tool call) whether
the word is really the stated part of speech in modern everyday English,
whether it is fit for a children's/teen reading corpus (no slurs, no adult
content, not archaic), and the earliest school band a reader typically meets
it in. Writes a per-phase report and a cleaned lexicon proposal; touches
nothing in the repo.

Usage:
    python lexicon_audit.py --out lex_audit
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from gen_ab import load_env

MODEL = "claude-haiku-4-5"
LEX_DIR = Path(__file__).resolve().parents[2] / "src" / "lifespan_learning" / "dataset_generation" / "prompt" / "config" / "lexicons"
BANDS = ["JK-SK", "grade 1-2", "grade 3-5", "grade 6-8", "grade 9-10", "grade 11", "grade 12"]
POS_NAME = {"verbs": "verb", "nouns": "noun", "adjectives": "adjective"}
BATCH = 120

TOOL = {
    "name": "record_words",
    "description": "Record the audit of every word in the batch, in the same order as given.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["words"],
        "properties": {
            "words": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["w", "pos_ok", "fit", "band", "flag"],
                    "properties": {
                        "w": {"type": "string", "description": "the word, exactly as given"},
                        "pos_ok": {"type": "boolean", "description": "true if this word is commonly used as the stated part of speech in modern everyday English (base form for verbs, singular for nouns)"},
                        "fit": {"type": "boolean", "description": "true if suitable for a graded reading corpus for ages 3-18: not archaic or dialect, not a slur or sexual/violent term, not a proper noun or nationality, not a misspelling or fragment"},
                        "band": {"type": "integer", "description": "0-6: earliest school band where a typical reader knows this word: 0=JK-SK, 1=grade 1-2, 2=grade 3-5, 3=grade 6-8, 4=grade 9-10, 5=grade 11, 6=grade 12+"},
                        "flag": {"type": "string", "description": "empty if pos_ok and fit; otherwise a 1-3 word reason (e.g. 'archaic', 'not a verb', 'slur', 'proper noun')"},
                    },
                },
            }
        },
    },
}


def audit_batch(client, pos: str, words: list[str]) -> list[dict]:
    import anthropic
    prompt = (
        f"Audit these {len(words)} words. Each is claimed to be a {POS_NAME[pos]} in a vocabulary list for a graded "
        f"children's and teen reading curriculum. Judge every word by modern, everyday North American English usage. "
        f"Record all {len(words)} in order with record_words.\n\n" + "\n".join(words)
    )
    for attempt in range(6):
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=8000, tools=[TOOL], tool_choice={"type": "tool", "name": "record_words"},
                messages=[{"role": "user", "content": prompt}],
            )
            for b in r.content:
                if b.type == "tool_use":
                    out = b.input["words"]
                    if len(out) != len(words):
                        raise ValueError(f"got {len(out)} of {len(words)}")
                    return out
            raise ValueError("no tool call")
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError, ValueError) as e:
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("gave up on batch")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("lex_audit"))
    ap.add_argument("--phases", default="0,1,2,3,4,5,6")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    load_env()
    out_dir = args.out if args.out.is_absolute() else Path(__file__).resolve().parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    import anthropic
    client = anthropic.Anthropic()

    jobs = []
    for ph in [int(p) for p in args.phases.split(",")]:
        lex = json.loads((LEX_DIR / f"phase_{ph}.json").read_text(encoding="utf-8"))
        for pos in ("verbs", "nouns", "adjectives"):
            words = lex[pos]
            for i in range(0, len(words), BATCH):
                jobs.append((ph, pos, i, words[i:i + BATCH]))
    print(f"{len(jobs)} batches")

    results: dict[tuple[int, str], list[dict]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(audit_batch, client, pos, words): (ph, pos, i) for ph, pos, i, words in jobs}
        for n, fut in enumerate(as_completed(futs), 1):
            ph, pos, i = futs[fut]
            results.setdefault((ph, pos), []).append((i, fut.result()))
            if n % 20 == 0:
                print(f"  {n}/{len(jobs)}")

    report_lines = []
    for ph in sorted({k[0] for k in results}):
        cleaned = {}
        report_lines.append(f"\n=== phase {ph} (target band {BANDS[ph]}) ===")
        for pos in ("verbs", "nouns", "adjectives"):
            rows = [w for _, chunk in sorted(results[(ph, pos)]) for w in chunk]
            bad_pos = [w for w in rows if not w["pos_ok"]]
            unfit = [w for w in rows if w["pos_ok"] and not w["fit"]]
            ok = [w for w in rows if w["pos_ok"] and w["fit"]]
            bands = Counter(w["band"] for w in ok)
            far_above = [w for w in ok if w["band"] > ph + 1]
            far_below = [w for w in ok if w["band"] < ph - 1]
            keep = [w["w"] for w in ok if abs(w["band"] - ph) <= 1]
            cleaned[pos] = keep
            report_lines.append(
                f"{pos:11s} n={len(rows):4d} not_pos={len(bad_pos):3d} unfit={len(unfit):3d} "
                f"band_dist={dict(sorted(bands.items()))} far_above={len(far_above)} far_below={len(far_below)} keep={len(keep)}"
            )
            report_lines.append(f"   not_pos e.g.: {[w['w'] + '(' + w['flag'] + ')' for w in bad_pos[:12]]}")
            report_lines.append(f"   unfit   e.g.: {[w['w'] + '(' + w['flag'] + ')' for w in unfit[:12]]}")
            report_lines.append(f"   far_above e.g.: {[w['w'] + str(w['band']) for w in far_above[:12]]}")
            report_lines.append(f"   far_below e.g.: {[w['w'] + str(w['band']) for w in far_below[:12]]}")
        (out_dir / f"phase_{ph}.audit.json").write_text(
            json.dumps({pos: [w for _, chunk in sorted(results[(ph, pos)]) for w in chunk] for pos in ("verbs", "nouns", "adjectives")}, indent=1),
            encoding="utf-8")
        (out_dir / f"phase_{ph}.cleaned.json").write_text(json.dumps(cleaned, indent=1), encoding="utf-8")
    report = "\n".join(report_lines)
    (out_dir / "report.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
