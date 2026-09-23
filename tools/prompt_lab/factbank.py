"""Build a verified, per-phase bank of real-world facts for story prompts.

Why: when the story model is asked to invent "one accurate fact" itself, the
judge found roughly a third of them muddled or false (hot tap on the right,
inconsistent base rates, wrong genetics). Injecting a pre-verified fact fixes
accuracy, lets facts be matched to the story's activity, and makes the
knowledge in each phase a known, fixed set that a later exam could probe.

Two passes:
  1. generate: Claude Sonnet 5 writes N facts per (phase, domain), each with a
     one-line story hook (cost: the 2026-09-23 Opus run was ~$0.13 a call).
  2. verify: Claude Opus 5 (a different, stronger model) checks every fact blind and
     marks true / false / misleading / too advanced; only "true" and
     band-appropriate facts survive.

Usage:
    python factbank.py --per-domain 20 --out facts
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from gen_ab import load_env

GEN_MODEL = "claude-sonnet-5"
VERIFY_MODEL = "claude-opus-5"
BANDS = ["junior/senior kindergarten (age 3-5)", "grades 1-2 (age 6-8)", "grades 3-5 (age 8-11)", "grades 6-8 (age 11-14)",
         "grades 9-10 (age 14-16)", "grade 11 (age 16-17)", "grade 12 (age 17-18)"]

# domain key -> description, per phase. Keys are shared across phases where
# the topic continues, so a story's activity can be mapped to a domain once.
DOMAINS = {
    0: {"animals": "animals: what they eat, where they live, how they move",
        "plants_weather": "plants, weather and the sky",
        "body": "the body and the five senses",
        "math": "counting, comparing amounts, and shapes",
        "tools": "everyday tools, materials and how things work at home",
        "people": "people's jobs and how a community works"},
    1: {"animals": "animals and their habitats and life cycles",
        "plants_weather": "plants, seasons, weather and the water cycle",
        "body": "the human body and staying healthy",
        "math": "numbers, addition, measuring and time",
        "tools": "simple machines and how everyday things work",
        "places": "maps, places and other countries",
        "history": "how people lived long ago"},
    2: {"animals": "animals, habitats and food chains",
        "plants_weather": "weather, climate, the water cycle and the Earth",
        "body": "the human body, nutrition and health",
        "math": "fractions, multiplication, measurement and simple data",
        "tools": "machines, inventions and how technology works",
        "places": "geography and cultures around the world",
        "history": "history of everyday things and famous events"},
    3: {"science": "the science behind everyday phenomena (light, sound, heat, forces)",
        "biology": "ecosystems, food webs and living things",
        "body": "body systems and health",
        "math": "ratio, percentage, probability, area and volume",
        "places": "geography, climate and cultures",
        "history": "historical events and why they happened",
        "tech": "how a technology works (engines, internet, electricity)"},
    4: {"science": "physics and chemistry ideas (energy, reactions, motion)",
        "biology": "biology, cells, genetics and evolution",
        "math": "statistics, probability and data",
        "economics": "the economics of everyday life (prices, trade-offs, interest)",
        "history": "historical events and their causes",
        "places": "geography and geology",
        "tech": "how technologies are engineered (bridges, software, batteries)"},
    5: {"science_method": "scientific method, evidence and experimental design",
        "economics": "economics and markets",
        "civics": "government, law and civic institutions",
        "psychology": "psychology and how people reason and decide",
        "history": "history and how it gets interpreted",
        "environment": "environmental systems and climate",
        "math": "mathematics as a way of reasoning (proof, modelling, logarithms, exponential growth)"},
    6: {"philosophy": "philosophy of knowledge and ethics",
        "economics": "economics and public policy",
        "science_method": "science and the limits of what it can show",
        "history": "history and historiography",
        "statistics": "statistics, uncertainty and risk",
        "tech": "technology and its effects on society",
        "language": "language, mind and meaning"},
}

GEN_TOOL = {
    "name": "record_facts",
    "description": "Record the generated facts.",
    "strict": True,
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["facts"],
        "properties": {"facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["fact", "hook"],
            "properties": {
                "fact": {"type": "string", "description": "One or two plain sentences stating one specific, verifiably true real-world fact, mechanism, number or method, phrased for the target band."},
                "hook": {"type": "string", "description": "Under 20 words: how a child's story could turn on this fact (something a character does, tries, or gets wrong)."},
            }}}},
    },
}

VERIFY_TOOL = {
    "name": "record_verdicts",
    "description": "Record one verdict per fact, in order.",
    "strict": True,
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["verdicts"],
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["i", "verdict", "reason"],
            "properties": {
                "i": {"type": "integer", "description": "index of the fact as given"},
                "verdict": {"type": "string", "enum": ["true", "false", "misleading", "unverifiable", "too_advanced", "too_easy"],
                            "description": "true = accurate as stated and suitable for the band; false = contains an error; misleading = technically defensible but would leave a wrong impression; unverifiable = opinion or vague; too_advanced / too_easy = accurate but wrong band by two or more bands"},
                "reason": {"type": "string", "description": "empty if true; otherwise under 15 words"},
            }}}},
    },
}


def call(client, **kw):
    import anthropic
    for attempt in range(6):
        try:
            return client.messages.create(**kw)
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("gave up")


def generate(client, phase: int, key: str, desc: str, n: int) -> list[dict]:
    prompt = (
        f"Write {n} distinct facts about {desc} for a graded reading curriculum. Target band: {BANDS[phase]}.\n\n"
        "Requirements for every fact:\n"
        "- Specific and verifiably true: a real mechanism, number, method, cause, or named thing. No opinions, no morals, no 'practice helps'.\n"
        "- A typical reader in the target band could understand it and would find it new or interesting; not trivially known to them, not beyond them.\n"
        "- Self-contained in one or two plain sentences; no jargon that the band would not know unless the sentence itself makes it clear.\n"
        "- Concrete enough that a short story could turn on it: a character could use it, test it, or be wrong about it.\n"
        "- Cover different sub-topics; do not repeat an idea in other words.\n"
        "- Prefer facts that are stable and uncontroversial; avoid anything culture-specific to one country unless it says which.\n"
        "Only include facts you are certain are true. Record them with record_facts."
    )
    r = call(client, model=GEN_MODEL, max_tokens=8000, thinking={"type": "adaptive"}, output_config={"effort": "medium"},
             tools=[GEN_TOOL], tool_choice={"type": "auto"}, messages=[{"role": "user", "content": prompt}])
    for b in r.content:
        if b.type == "tool_use":
            return [{"phase": phase, "domain": key, **f} for f in b.input["facts"]]
    return []


def verify(client, phase: int, facts: list[dict]) -> list[dict]:
    listing = "\n".join(f"{i}. {f['fact']}" for i, f in enumerate(facts))
    prompt = (
        f"You are fact-checking sentences written for readers in {BANDS[phase]}. For each, decide whether it is accurate "
        f"as stated and suitable for that band. Be strict: any factual error, overstatement or misleading simplification "
        f"fails. Record one verdict per fact with record_verdicts.\n\n{listing}"
    )
    r = call(client, model=VERIFY_MODEL, max_tokens=8000, thinking={"type": "adaptive"}, output_config={"effort": "medium"},
             tools=[VERIFY_TOOL], tool_choice={"type": "auto"}, messages=[{"role": "user", "content": prompt}])
    verdicts = {}
    for b in r.content:
        if b.type == "tool_use":
            for v in b.input["verdicts"]:
                verdicts[v["i"]] = v
    out = []
    for i, f in enumerate(facts):
        v = verdicts.get(i, {"verdict": "unverifiable", "reason": "no verdict"})
        out.append({**f, "verdict": v["verdict"], "reason": v["reason"]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-domain", type=int, default=15)
    ap.add_argument("--phases", default="0,1,2,3,4,5,6")
    ap.add_argument("--out", type=Path, default=Path("facts"))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    load_env()
    out_dir = args.out if args.out.is_absolute() else Path(__file__).resolve().parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    import anthropic
    client = anthropic.Anthropic()
    phases = [int(p) for p in args.phases.split(",")]

    # pass 1 (resumable: each (phase, domain) result is cached on disk as soon
    # as it arrives, so a run killed by a billing or network error loses
    # nothing already paid for)
    cache_dir = out_dir / "_cache"
    cache_dir.mkdir(exist_ok=True)

    def gen_cached(ph, k, d):
        p = cache_dir / f"gen_{ph}_{k}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        got = generate(client, ph, k, d, args.per_domain)
        p.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        return got

    gen_jobs = [(ph, k, d) for ph in phases for k, d in DOMAINS[ph].items()]
    facts: dict[int, list[dict]] = {ph: [] for ph in phases}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(gen_cached, ph, k, d): (ph, k) for ph, k, d in gen_jobs}
        for fut in as_completed(futs):
            ph, k = futs[fut]
            got = fut.result()
            facts[ph].extend(got)
            print(f"  generated phase {ph} {k}: {len(got)}", flush=True)
    for ph in phases:
        facts[ph].sort(key=lambda f: (f["domain"], f["fact"]))

    # pass 2 (verify in chunks of 40; cached the same way)
    def verify_cached(ph, i, chunk):
        p = cache_dir / f"ver_{ph}_{i}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        got = verify(client, ph, chunk)
        p.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        return got

    verified: dict[int, list[dict]] = {ph: [] for ph in phases}
    ver_jobs = [(ph, i, facts[ph][i:i + 60]) for ph in phases for i in range(0, len(facts[ph]), 60)]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(verify_cached, ph, i, chunk): ph for ph, i, chunk in ver_jobs}
        for fut in as_completed(futs):
            verified[futs[fut]].extend(fut.result())
    summary = []
    for ph in phases:
        rows = verified[ph]
        keep = [r for r in rows if r["verdict"] == "true"]
        (out_dir / f"phase_{ph}.all.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
        (out_dir / f"phase_{ph}.json").write_text(
            json.dumps({"phase": ph, "band": BANDS[ph], "generated_by": GEN_MODEL, "verified_by": VERIFY_MODEL,
                        "facts": [{"domain": r["domain"], "fact": r["fact"], "hook": r["hook"]} for r in keep]},
                       indent=1, ensure_ascii=False), encoding="utf-8")
        from collections import Counter
        c = Counter(r["verdict"] for r in rows)
        summary.append(f"phase {ph}: {len(rows)} generated, kept {len(keep)}; verdicts {dict(c)}")
        rejected = [r for r in rows if r["verdict"] != "true"][:6]
        for r in rejected:
            summary.append(f"    [{r['verdict']}] {r['fact'][:100]} -- {r['reason']}")
    print("\n".join(summary))
    (out_dir / "summary.txt").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
