"""Score generated stories: cheap text metrics + a blind judge.

Preferred judge: a subagent (no API spend). `--export` writes the blind
stories and a separate targets file; the subagent writes
<variant>.judged.jsonl ({"idx": i, "j": {...}} per line, same fields as
JUDGE_TOOL) and a plain run then reports from that file. The Opus API judge
below is the fallback and costs ~$0.02 a story.

The judge never sees the prompt or the target age. It guesses the grade band
from the text alone, which is the property the experiment needs (phases must
be tellable apart), then rates age fit against the revealed target.

Usage:
    python judge.py runs/r1 --variants baseline,v1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from gen_ab import load_env

JUDGE_MODEL = "claude-opus-5"
BANDS = ["JK-SK (age 3-5)", "grade 1-2 (age 6-8)", "grade 3-5 (age 8-11)", "grade 6-8 (age 11-14)",
         "grade 9-10 (age 14-16)", "grade 11 (age 16-17)", "grade 12 (age 17-18)"]

JUDGE_TOOL = {
    "name": "record_assessment",
    "description": "Record the assessment of one story.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["guessed_band", "reading_level_fit", "educational_value", "learned_fact", "thinking_skill",
                     "coherence", "naturalness", "has_title_or_markup", "lecture_like", "notes"],
        "properties": {
            "guessed_band": {"type": "string", "enum": BANDS,
                             "description": "Blind guess, from the text alone, of the school band this story was written for."},
            "reading_level_fit": {"type": "integer",
                                  "description": "After the target age is revealed: 1 = badly mismatched, 5 = vocabulary, sentence structure and theme all fit the target age."},
            "educational_value": {"type": "integer",
                                  "description": "1 = nothing to learn; 5 = a reader of the target age would come away knowing or understanding something new and true (a fact, a skill, a way of thinking, a word used so its meaning is clear)."},
            "learned_fact": {"type": "string", "description": "The single most concrete, accurate thing a reader learns from this story, quoted or paraphrased; empty string if none. If anything stated as fact is false, say so here."},
            "thinking_skill": {"type": "string", "description": "In one phrase, the most advanced kind of reasoning the main character actually performs in the story (e.g. 'notices one cause and effect', 'tests a variable', 'weighs two explanations')."},
            "coherence": {"type": "integer", "description": "Plot logic and consistency. 5 = fully coherent."},
            "naturalness": {"type": "integer", "description": "5 = reads like a good human-written story; 1 = reads like a checklist being ticked (forced vocabulary, bolted-on lesson)."},
            "has_title_or_markup": {"type": "boolean", "description": "True if the text contains a title line, heading, markdown, emoji or a list."},
            "lecture_like": {"type": "boolean", "description": "True if the educational content is delivered as a lecture or explicit definition rather than through the story."},
            "notes": {"type": "string", "description": "One or two sentences: the biggest weakness."},
        },
    },
}

JUDGE_SYSTEM = (
    "You are an expert in children's and young-adult literature and in reading-level assessment "
    "(Lexile, grade-band vocabulary, sentence complexity, Piagetian stages of reasoning). "
    "You assess stories generated for a graded reading curriculum. Be strict and specific; never inflate scores."
)


def judge_one(client, story: str, age: int, grade: str) -> dict:
    import anthropic
    user = (
        "STEP 1 (blind): Read the story below and guess which school band it was written for.\n"
        "STEP 2: The story was actually written for a reader aged "
        f"{age} ({grade}). Rate it against that target.\n\n"
        "Record your assessment with the record_assessment tool.\n\n"
        f"<story>\n{story}\n</story>"
    )
    for attempt in range(5):
        try:
            r = client.messages.create(
                model=JUDGE_MODEL, max_tokens=2000, system=JUDGE_SYSTEM,
                thinking={"type": "adaptive"}, output_config={"effort": "low"},
                tools=[JUDGE_TOOL], tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": user}],
            )
            for b in r.content:
                if b.type == "tool_use" and b.name == "record_assessment":
                    return dict(b.input)
            return {"error": "no tool call", "text": "".join(getattr(b, "text", "") for b in r.content)}
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            time.sleep(2 ** attempt)
    return {"error": "gave up"}


# ---------------------------------------------------------------------------
# Text metrics
# ---------------------------------------------------------------------------
_SENT = re.compile(r"[.!?]+(?:\s|$)")


def text_metrics(row: dict) -> dict:
    s = row["story"]
    words = re.findall(r"[A-Za-z']+", s)
    sents = [x for x in _SENT.split(s) if x.strip()]
    paras = [p for p in s.split("\n\n") if p.strip()]
    lower = s.lower()
    first_line = s.strip().splitlines()[0] if s.strip() else ""
    title_like = (len(first_line.split()) <= 8 and not first_line.rstrip().endswith((".", "!", "?", '"', "'"))) or first_line.startswith("#")
    return {
        "words": len(words),
        "sentences": len(sents),
        "mean_sent_len": round(len(words) / max(1, len(sents)), 1),
        "paragraphs": len(paras),
        "title_like": bool(title_like),
        "markdown": bool(re.search(r"^\s*#|\*\*|^\s*[-*] ", s, re.M)),
        "used_verb": row["verb"].lower()[:4] in lower,
        "used_noun": row["noun"].lower() in lower,
        "used_adj": row["adjective"].lower() in lower,
        "curly_quotes": bool(re.search(r"[“”‘’]", s)),
        "em_dash": "—" in s,
        "truncated": row["stop_reason"] == "max_tokens",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--variants", default="baseline,v1")
    ap.add_argument("--no-llm", action="store_true", help="text metrics only, or report from an existing <variant>.judged.jsonl")
    ap.add_argument("--export", action="store_true", help="write <variant>.blind.jsonl (idx, story) and <variant>.targets.json (idx -> age, grade) for a subagent judge, then exit")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    load_env()
    run_dir = args.run_dir if args.run_dir.is_absolute() else Path(__file__).resolve().parent / args.run_dir

    import anthropic
    client = anthropic.Anthropic()

    for v in args.variants.split(","):
        rows = [json.loads(l) for l in (run_dir / f"{v}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in rows:
            r["m"] = text_metrics(r)
        if args.export:
            (run_dir / f"{v}.blind.jsonl").write_text("
".join(json.dumps({"idx": r["idx"], "story": r["story"]}, ensure_ascii=False) for r in sorted(rows, key=lambda r: r["idx"])) + "
", encoding="utf-8")
            (run_dir / f"{v}.targets.json").write_text(json.dumps({str(r["idx"]): {"age": r["age"], "grade": r["grade"]} for r in rows}, indent=1), encoding="utf-8")
            print(f"exported {v}: {len(rows)} stories -> {v}.blind.jsonl, {v}.targets.json")
            continue
        if not args.no_llm:
            cache = run_dir / f"{v}.judged.jsonl"
            done = {}
            if cache.exists():
                for l in cache.read_text(encoding="utf-8").splitlines():
                    if l.strip():
                        d = json.loads(l); done[d["idx"]] = d["j"]
            todo = [r for r in rows if r["idx"] not in done]
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(judge_one, client, r["story"], r["age"], r["grade"]): r for r in todo}
                for fut in as_completed(futs):
                    r = futs[fut]; r["j"] = fut.result()
            for r in rows:
                if r["idx"] in done:
                    r["j"] = done[r["idx"]]
            cache.write_text("\n".join(json.dumps({"idx": r["idx"], "j": r["j"]}, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

        # ---- report ----
        print(f"\n=== {v}: {len(rows)} stories ===")
        m_keys = ["words", "mean_sent_len", "paragraphs"]
        b_keys = ["title_like", "markdown", "used_verb", "used_noun", "used_adj", "curly_quotes", "em_dash", "truncated"]
        print("phase | n | " + " | ".join(m_keys) + " | " + " | ".join(b_keys))
        for ph in sorted({r["phase"] for r in rows}):
            rs = [r for r in rows if r["phase"] == ph]
            means = [f"{statistics.mean(r['m'][k] for r in rs):.0f}" for k in m_keys]
            rates = [f"{sum(r['m'][k] for r in rs)}/{len(rs)}" for k in b_keys]
            print(f"  {ph}   | {len(rs)} | " + " | ".join(means) + " | " + " | ".join(rates))
        if not args.no_llm:
            ok = [r for r in rows if "error" not in r["j"]]
            print(f"LLM judge ({len(ok)} scored):")
            print("phase | band-exact | band-within-1 | rl_fit | edu | coh | natural | title/markup | lecture")
            for ph in sorted({r["phase"] for r in ok}):
                rs = [r for r in ok if r["phase"] == ph]
                exact = sum(BANDS.index(r["j"]["guessed_band"]) == ph for r in rs)
                within = sum(abs(BANDS.index(r["j"]["guessed_band"]) - ph) <= 1 for r in rs)
                f = lambda k: f"{statistics.mean(r['j'][k] for r in rs):.2f}"
                print(f"  {ph}   | {exact}/{len(rs)} | {within}/{len(rs)} | {f('reading_level_fit')} | {f('educational_value')} | {f('coherence')} | {f('naturalness')} | {sum(r['j']['has_title_or_markup'] for r in rs)} | {sum(r['j']['lecture_like'] for r in rs)}")
            f = lambda k: f"{statistics.mean(r['j'][k] for r in ok):.2f}"
            exact = sum(BANDS.index(r["j"]["guessed_band"]) == r["phase"] for r in ok)
            within = sum(abs(BANDS.index(r["j"]["guessed_band"]) - r["phase"]) <= 1 for r in ok)
            print(f"  ALL | {exact}/{len(ok)} | {within}/{len(ok)} | {f('reading_level_fit')} | {f('educational_value')} | {f('coherence')} | {f('naturalness')} | {sum(r['j']['has_title_or_markup'] for r in ok)} | {sum(r['j']['lecture_like'] for r in ok)}")
            # confusion: phase -> guessed band index
            conf = {}
            for r in ok:
                conf.setdefault(r["phase"], []).append(BANDS.index(r["j"]["guessed_band"]))
            print("  guessed bands per phase:", {k: sorted(v) for k, v in sorted(conf.items())})


if __name__ == "__main__":
    main()
