"""Candidate prompt templates. Each render_<name>(row) takes the captured
row from gen_ab.build_configs (row["cfg"] is the repo's PromptConfig,
row["kind"] is exposure | experience | arc, row["phase"] the phase id) and
returns the prompt text. Extra choices (knowledge domain) are derived from a
hash of the config, never from the shared rng, so the sampled configuration
stays identical to the baseline's.
"""
from __future__ import annotations

import hashlib

FRAMING = {
    0: "You write stories for young children who are just learning to understand the world.",
    1: "You write stories for children who are learning to read on their own.",
    2: "You write stories for children in the middle grades of elementary school.",
    3: "You write short fiction for middle-school readers.",
    4: "You write short fiction for early high-school readers.",
    5: "You write short fiction for older high-school readers.",
    6: "You write short fiction for readers finishing high school and starting college.",
}

# Per-phase "thinking move", written from phases.yaml's developmental descriptions.
THINKING = {
    0: "{name} notices one simple cause and its effect (something happens because of one clear reason) and says it in simple words.",
    1: "{name} follows one clear rule with several steps in order (first, next, then, last) and sees it work.",
    2: "{name} compares or sorts things by more than one feature at once, or works out how two things relate (bigger and heavier, half as many, the same kind but different).",
    3: "{name} reasons about something that cannot be seen directly (a hidden cause, a pattern, a rule) and tests a simple idea about it.",
    4: "{name} deliberately changes one thing to see what happens, or reasons through a what-if, and draws a conclusion from the result.",
    5: "{name} weighs two competing explanations against the evidence, notices an assumption behind one of them, and decides what the evidence can and cannot show.",
    6: "{name} brings two different perspectives or ways of thinking together into a considered position, and is honest about what stays uncertain.",
}

DOMAINS = {
    0: ["animals", "plants and weather", "the body and the five senses", "counting and shapes", "everyday tools and how they are used", "people's jobs"],
    1: ["animals and where they live", "plants, seasons and weather", "the human body", "numbers, counting and measuring", "how simple machines work", "maps and places", "how things were done long ago"],
    2: ["animals and their habitats", "weather and the water cycle", "the human body and health", "numbers, fractions and measuring", "how machines and inventions work", "geography and other cultures", "history of everyday things"],
    3: ["the science behind an everyday phenomenon", "ecosystems and food webs", "a body system", "a mathematical idea (ratio, probability, area)", "geography or a culture", "a historical event and why it happened", "how a technology works"],
    4: ["a physics or chemistry idea", "biology or genetics", "statistics or probability", "the economics of everyday life", "a historical event and its causes", "geography or geology", "how a technology is engineered"],
    5: ["scientific method and the strength of evidence", "economics or markets", "government, law or civics", "psychology and how people reason", "history and how it gets interpreted", "environmental systems", "mathematics as a way of reasoning"],
    6: ["the philosophy of knowledge or ethics", "economics and public policy", "science and the limits of what it can show", "history and historiography", "statistics, uncertainty and risk", "technology and its effects on society", "language, mind and meaning"],
}

WORDS_PER_PARAGRAPH = {0: 45, 1: 55, 2: 65, 3: 75, 4: 85, 5: 90, 6: 90}


def _pick(seq, *keys) -> str:
    h = hashlib.sha256("|".join(str(k) for k in keys).encode("utf-8")).hexdigest()
    return seq[int(h, 16) % len(seq)]


def _what_happens(row) -> str:
    c = row["cfg"]
    if row["kind"] == "exposure":
        return f"Through what {c.name} sees, hears and does, the story naturally introduces {c.goal}."
    if row["kind"] == "experience":
        return f"{c.name} is {c.goal}."
    return f"{c.name} is learning something new. What {c.name} is learning: {c.goal}."


def _a(n: int) -> str:
    return "an" if str(n)[0] in "8" or n in (11, 18) else "a"


def render_v1(row) -> str:
    c = row["cfg"]
    ph = row["phase"]
    domain = _pick(DOMAINS[ph], "domain", c.name, c.noun, c.location, ph)
    wpp = WORDS_PER_PARAGRAPH[ph]
    lo, hi = max(c.min_paragraphs, 2) * wpp, c.max_paragraphs * wpp
    behaviors = "; ".join(b[0].lower() + b[1:] for b in c.tone.behaviors)
    features = f"Also: {c.features}.\n" if c.features else ""
    audience = "child" if ph < 4 else "reader"
    return f"""{FRAMING[ph]}

Write a story for {_a(c.age)} {c.age}-year-old {audience}.
Reading level: {c.reading_level}
Length: {c.min_paragraphs}-{c.max_paragraphs} paragraphs, about {lo}-{hi} words.

Main character: {_a(c.age)} {c.age}-year-old {c.gender} named {c.name}.
Setting: {c.location.strip()}.
What happens: {_what_happens(row)}

Thinking the story should show: {THINKING[ph].format(name=c.name)}
Something to learn: include one accurate, real-world thing about {domain} that a reader this age could learn from the story. Show it through what {c.name} does, notices or discovers, never as a lecture or a definition.

Vocabulary: use the verb "{c.verb}", the noun "{c.noun}" and the adjective "{c.adjective}", each at least once, in sentences that make its meaning clear from context.

Tone: {c.tone.key}: {behaviors}.
{features}
Format rules:
- Plain prose only: no title, no heading, no markdown, no lists, no emoji.
- Start with the first sentence of the story and stop at its last sentence. Do not add a moral summary, a note or a question after the story.
- Use standard punctuation and straight quotation marks.
- The story must be appropriate for {_a(c.age)} {c.age}-year-old {audience}."""


# ---------------------------------------------------------------------------
# v2: format rules first; knowledge must drive the plot (no lectures, no stated
# moral); conflict required; paragraph cap; reader-assumption line for
# phases >= 3; mentor speeches banned.
# ---------------------------------------------------------------------------
READER_ASSUMPTION = {
    3: "Assume the reader is a capable middle-schooler: do not explain things an 11-year-old already knows.",
    4: "Assume the reader is an intelligent high-school student: leave things implied, avoid explaining what a 14-year-old already knows, and let the character be wrong before being right.",
    5: "Assume the reader is an intelligent 16-year-old who reads adult fiction: no hand-holding, no explaining what they already know, and the ending may stay open.",
    6: "Assume the reader is an intelligent 17-year-old about to start college: write with the restraint of literary fiction, trust them to infer, and let the ending stay unresolved if that is truer.",
}

FORMAT_RULES = """Rules for the reply:
- Reply with the story text only. Begin with the first sentence of the story. No title, no heading, no preamble.
- Plain prose paragraphs only: no markdown, no lists, no emoji, no notes after the story.
- End on an action, an image or a line of dialogue, never on a stated lesson, summary or reflection."""


def render_v2(row, with_thinking: bool = True) -> str:
    c = row["cfg"]
    ph = row["phase"]
    domain = _pick(DOMAINS[ph], "domain", c.name, c.noun, c.location, ph)
    wpp = WORDS_PER_PARAGRAPH[ph]
    lo, hi = max(c.min_paragraphs, 2) * wpp, c.max_paragraphs * wpp
    behaviors = "; ".join(b[0].lower() + b[1:] for b in c.tone.behaviors)
    features = f"Also: {c.features}.\n" if c.features else ""
    audience = "child" if ph < 4 else "reader"
    assumption = (READER_ASSUMPTION[ph] + "\n") if ph in READER_ASSUMPTION else ""
    thinking = f"Thinking the story shows: {THINKING[ph].format(name=c.name)}\n" if with_thinking else ""
    speech_rule = ("- No adult, teacher or mentor explains the idea in a speech; the character works it out or finds it out.\n"
                   if ph >= 2 else "- Nobody explains the idea in a speech; " + c.name + " finds it out by doing.\n")
    return f"""{FORMAT_RULES}

{FRAMING[ph]}
{assumption}
Write a story for {_a(c.age)} {c.age}-year-old {audience}.
Reading level: {c.reading_level}
Length: {c.min_paragraphs}-{c.max_paragraphs} paragraphs (never more than {c.max_paragraphs}), about {lo}-{hi} words.

Main character: {_a(c.age)} {c.age}-year-old {c.gender} named {c.name}.
Setting: {c.location.strip()}.
What happens: {_what_happens(row)}
The story needs a real problem or want that drives it, and something concrete has to happen; do not summarize feelings, show events.

{thinking}Knowledge in the plot: the events should turn on one accurate, real-world idea about {domain}. {c.name} uses it, discovers it, or gets it wrong and finds out. Requirements:
- The idea is specific and true (a real fact, mechanism, number or method), not a general attitude like "practice helps".
{speech_rule}- The narrator never defines or explains it; the reader picks it up from what happens.

Vocabulary: use the verb "{c.verb}", the noun "{c.noun}" and the adjective "{c.adjective}", each at least once, in sentences that make its meaning clear from context. Weave them in naturally; never draw attention to them.

Tone: {c.tone.key}: {behaviors}.
{features}
The story must be appropriate for {_a(c.age)} {c.age}-year-old {audience}."""


def render_v3(row) -> str:
    """v2 without the per-phase thinking-move line (ablation)."""
    return render_v2(row, with_thinking=False)


# ---------------------------------------------------------------------------
# v4: v2 + a verified fact from the fact bank (facts/phase_{i}.json), matched to
# the story's activity; scene rule for older phases; punctuation rule.
# ---------------------------------------------------------------------------
import json as _json
from pathlib import Path as _Path

_FACTS_DIR = _Path(__file__).resolve().parent / "facts"
_FACT_CACHE: dict[int, list[dict]] = {}

CONTENT_DOMAIN_PREFS = {
    "learning_physics": ["science", "tools", "tech"], "learning_chemistry": ["science", "tools"],
    "learning_biology": ["biology", "animals", "plants_weather", "body"], "learning_history": ["history"],
    "learning_cooking": ["science", "math", "body", "tools"], "learning_to_code": ["tech", "math", "statistics"],
    "learning_music": ["science", "tools", "history", "language"], "learning_art": ["tools", "math", "history"],
    "learning_sports": ["body", "science", "math"], "learning_hygiene": ["body", "biology"],
    "learning_religious_or_cultural_practices": ["places", "history", "philosophy"],
    "playing_sports": ["body", "science", "math", "psychology"],
    "watching_sports": ["body", "science", "statistics", "psychology", "economics"],
    "playing_music": ["science", "history", "language", "tools"], "drawing_or_crafting": ["tools", "math", "science", "tech"],
    "cooking_or_baking": ["science", "math", "body"], "religious_or_cultural_events": ["places", "history", "philosophy", "civics"],
    "first_day_of_school": ["people", "psychology", "civics", "math"], "puberty": ["body", "biology", "psychology"],
    "first_date": ["psychology", "economics", "language"],
    "number_words": ["math"], "object_categories": ["animals", "tools"], "time_words": ["plants_weather", "math"],
    "social_rules": ["people", "civics", "psychology"], "colors": ["science", "plants_weather", "animals"], "shapes": ["math", "tools"],
    "emotions": ["body", "psychology", "animals"], "daily_routines": ["body"], "polite_language": ["people", "language"],
    "pretend_play": ["animals", "people", "tools"], "safety_concepts": ["body", "tools", "science"],
    "classroom_language_patterns": ["math", "people", "science"], "community_roles": ["people", "civics", "economics"],
    "simple_cause_effect": ["science", "tools", "plants_weather"], "academic_vocabulary_exposure": [],
    "group_norms": ["psychology", "people", "civics"], "media_literacy_awareness": ["psychology", "tech", "statistics"],
    "perspective_exposure": ["psychology", "history", "philosophy"], "digital_environment_patterns": ["tech", "psychology"],
    "identity_language": ["psychology", "language", "places"], "abstract_discourse_patterns": ["philosophy", "math", "science_method"],
    "civic_process_awareness": ["civics", "economics", "history"], "long_term_consequence_patterns": ["economics", "environment", "statistics"],
    "professional_communication_norms": ["economics", "language", "civics"], "ethical_framework_language": ["philosophy", "economics"],
    "systems_thinking_patterns": ["environment", "economics", "tech"],
}


def _facts(phase: int) -> list[dict]:
    if phase not in _FACT_CACHE:
        _FACT_CACHE[phase] = _json.loads((_FACTS_DIR / f"phase_{phase}.json").read_text(encoding="utf-8"))["facts"]
    return _FACT_CACHE[phase]


def pick_fact(row) -> dict:
    c = row["cfg"]
    ph = row["phase"]
    facts = _facts(ph)
    available = {f["domain"] for f in facts}
    prefs = [d for d in CONTENT_DOMAIN_PREFS.get(row["content_key"], []) if d in available]
    pool = [f for f in facts if f["domain"] == prefs[0]] if prefs else facts
    return _pick(pool, "fact", c.name, c.noun, c.verb, c.location, ph)


def render_v4(row) -> str:
    c = row["cfg"]
    ph = row["phase"]
    fact = pick_fact(row)
    wpp = WORDS_PER_PARAGRAPH[ph]
    lo, hi = max(c.min_paragraphs, 2) * wpp, c.max_paragraphs * wpp
    behaviors = "; ".join(b[0].lower() + b[1:] for b in c.tone.behaviors)
    features = f"Also: {c.features}.\n" if c.features else ""
    audience = "child" if ph < 4 else "reader"
    assumption = (READER_ASSUMPTION[ph] + "\n") if ph in READER_ASSUMPTION else ""
    speech_rule = ("- No adult, teacher or mentor explains it in a speech; " + c.name + " works it out or finds it out.\n"
                   if ph >= 2 else "- Nobody explains it in a speech; " + c.name + " finds it out by doing.\n")
    scene_rule = ("- At least half of the story is scene: people doing and saying things in a specific place. No paragraph is pure reflection.\n"
                  if ph >= 3 else "")
    return f"""{FORMAT_RULES}
- Use ordinary punctuation: commas, periods and straight quotation marks; avoid dashes.

{FRAMING[ph]}
{assumption}
Write a story for {_a(c.age)} {c.age}-year-old {audience}.
Reading level: {c.reading_level}
Length: {c.min_paragraphs}-{c.max_paragraphs} paragraphs (never more than {c.max_paragraphs}), about {lo}-{hi} words.

Main character: {_a(c.age)} {c.age}-year-old {c.gender} named {c.name}.
Setting: {c.location.strip()}.
What happens: {_what_happens(row)}
The story needs a real problem or want that drives it, and something concrete has to happen; do not summarize feelings, show events.

Thinking the story shows: {THINKING[ph].format(name=c.name)}
Knowledge in the plot: the events turn on this real fact: "{fact['fact']}" (one way it could come up: {fact['hook']}). {c.name} uses it, discovers it, or gets it wrong and finds out. Requirements:
- Keep the fact accurate as stated. Do not add other technical claims unless you are certain they are true.
{speech_rule}- The narrator never defines or explains it; the reader picks it up from what happens.
{scene_rule}
Vocabulary: use the verb "{c.verb}", the noun "{c.noun}" and the adjective "{c.adjective}", each at least once, in sentences that make its meaning clear from context. Weave them in naturally; never draw attention to them.

Tone: {c.tone.key}: {behaviors}.
{features}
The story must be appropriate for {_a(c.age)} {c.age}-year-old {audience}."""
