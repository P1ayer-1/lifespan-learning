"""The story prompt template, shared by every content type.

One template, keyed by phase, replaces the three near-identical f-strings
that used to live in exposures.py, experiences.py and arcs.py. It is the
2026-09-23 "v2" template chosen by A/B measurement against the 2026-09-22
template on Claude Haiku 4.5 (docs/DECISIONS.md in the Lifespan repo,
2026-09-23, "prompt template"), plus the fact slot from "v4":

- Reply rules come first and are explicit (no title, no markdown, end on an
  action). Titles went from 41/42 stories to 0/21.
- A per-phase "thinking move" written from phases.yaml's developmental
  descriptions, so the phases differ in the kind of reasoning shown, not
  only in sentence length. A blind judge placed 19/21 stories within one
  band of the target (baseline 16/21) and 11/21 exactly (baseline 8/21).
- "Knowledge in the plot": every story turns on one real-world idea. When a
  verified fact bank exists for the phase (config/facts/phase_{id}.json) the
  fact is injected verbatim; otherwise the model is asked for one about a
  sampled domain (the judge found ~1/3 of self-invented facts wrong, which
  is why the fact bank exists).
- Lectures banned: no mentor speeches, the narrator never explains, the
  story cannot end on a stated moral. Judge "lecture-like" rate 16/21 -> 5/21;
  naturalness 2.4 -> 3.3 on a 5-point scale.
- Older phases get a reader-assumption line (no hand-holding) and a scene
  rule (no paragraph of pure reflection).

Everything here is deterministic given the PromptConfig; no randomness.
"""
from __future__ import annotations

from .generation_configs import PromptConfig

# Per-phase thinking move, from phases.yaml's descriptions.
THINKING_BY_PHASE = {
    0: "{name} notices one simple cause and its effect (something happens because of one clear reason) and says it in simple words.",
    1: "{name} follows one clear rule with several steps in order (first, next, then, last) and sees it work.",
    2: "{name} compares or sorts things by more than one feature at once, or works out how two things relate (bigger and heavier, half as many, the same kind but different).",
    3: "{name} reasons about something that cannot be seen directly (a hidden cause, a pattern, a rule) and tests a simple idea about it.",
    4: "{name} deliberately changes one thing to see what happens, or reasons through a what-if, and draws a conclusion from the result.",
    5: "{name} weighs two competing explanations against the evidence, notices an assumption behind one of them, and decides what the evidence can and cannot show.",
    6: "{name} brings two different perspectives or ways of thinking together into a considered position, and is honest about what stays uncertain.",
}

READER_ASSUMPTION_BY_PHASE = {
    3: "Assume the reader is a capable middle-schooler: do not explain things an 11-year-old already knows.",
    4: "Assume the reader is an intelligent high-school student: leave things implied, avoid explaining what a 14-year-old already knows, and let the character be wrong before being right.",
    5: "Assume the reader is an intelligent 16-year-old who reads adult fiction: no hand-holding, no explaining what they already know, and the ending may stay open.",
    6: "Assume the reader is an intelligent 17-year-old about to start college: write with the restraint of literary fiction, trust them to infer, and let the ending stay unresolved if that is truer.",
}

# Rough words per paragraph per phase; only used to state a word range so
# the paragraph count is not the model's only length signal.
WORDS_PER_PARAGRAPH = {0: 45, 1: 55, 2: 65, 3: 75, 4: 85, 5: 90, 6: 90}

FORMAT_RULES = """Rules for the reply:
- Reply with the story text only. Begin with the first sentence of the story. No title, no heading, no preamble.
- Plain prose paragraphs only: no markdown, no lists, no emoji, no notes after the story.
- End on an action, an image or a line of dialogue, never on a stated lesson, summary or reflection.
- Use ordinary punctuation: commas, periods and straight quotation marks; avoid dashes."""

# From this phase up the closing line says "reader", never "child".
READER_NOT_CHILD_FROM_PHASE = 4


def article(n: int) -> str:
    """'an 8-year-old', 'an 11-year-old', 'an 18-year-old', otherwise 'a'."""
    return "an" if n in (8, 11, 18) or (80 <= n <= 89) else "a"


def _what_happens(cfg: PromptConfig) -> str:
    if cfg.kind == "exposure":
        return f"Through what {cfg.name} sees, hears and does, the story naturally introduces {cfg.goal}."
    if cfg.kind == "experience":
        return f"{cfg.name} is {cfg.goal}."
    # learning arcs: the goal is a noun phrase ("basic coding concepts such as ...")
    return f"{cfg.name} is learning something new. What {cfg.name} is learning: {cfg.goal}."


def _knowledge_block(cfg: PromptConfig) -> str:
    name, ph = cfg.name, cfg.phase
    speech_rule = (
        f"- No adult, teacher or mentor explains it in a speech; {name} works it out or finds it out."
        if ph >= 2 else f"- Nobody explains it in a speech; {name} finds it out by doing."
    )
    scene_rule = (
        "\n- At least half of the story is scene: people doing and saying things in a specific place. No paragraph is pure reflection."
        if ph >= 3 else ""
    )
    if cfg.fact:
        hook = f" (one way it could come up: {cfg.fact_hook})" if cfg.fact_hook else ""
        head = (
            f'Knowledge in the plot: the events turn on this real fact: "{cfg.fact}"{hook}. '
            f"{name} uses it, discovers it, or gets it wrong and finds out. Requirements:\n"
            "- Keep the fact accurate as stated: every number, direction and comparison in it stays exactly as given. "
            "Do not explain why it is true, and do not add mechanisms, numbers, dates or causes beyond it; "
            "the story shows the fact in action, nothing more."
        )
    else:
        head = (
            f"Knowledge in the plot: the events should turn on one accurate, real-world idea about {cfg.domain}. "
            f"{name} uses it, discovers it, or gets it wrong and finds out. Requirements:\n"
            "- The idea is specific and true (a real fact, mechanism, number or method), not a general attitude like \"practice helps\"."
        )
    return (
        f"{head}\n{speech_rule}\n"
        "- The narrator never defines or explains it; the reader picks it up from what happens."
        f"{scene_rule}"
    )


def render(cfg: PromptConfig) -> str:
    ph = cfg.phase
    wpp = WORDS_PER_PARAGRAPH[ph]
    lo, hi = max(cfg.min_paragraphs, 2) * wpp, cfg.max_paragraphs * wpp
    audience = "reader" if ph >= READER_NOT_CHILD_FROM_PHASE else "child"
    a = article(cfg.age)
    behaviors = "; ".join(b[0].lower() + b[1:] for b in cfg.tone.behaviors)
    assumption = f"{READER_ASSUMPTION_BY_PHASE[ph]}\n" if ph in READER_ASSUMPTION_BY_PHASE else ""
    features = f"Also: {cfg.features}.\n" if cfg.features else ""
    return f"""{FORMAT_RULES}

{cfg.framing}
{assumption}
Write a story for {a} {cfg.age}-year-old {audience}.
Reading level: {cfg.reading_level}
Length: {cfg.min_paragraphs}-{cfg.max_paragraphs} paragraphs (never more than {cfg.max_paragraphs}), about {lo}-{hi} words.

Main character: {a} {cfg.age}-year-old {cfg.gender} named {cfg.name}.
Setting: {cfg.location.strip()}.
What happens: {_what_happens(cfg)}
The story needs a real problem or want that drives it, and something concrete has to happen; do not summarize feelings, show events.

Thinking the story shows: {THINKING_BY_PHASE[ph].format(name=cfg.name)}
{_knowledge_block(cfg)}

Vocabulary: where they fit naturally, use the verb "{cfg.verb}", the noun "{cfg.noun}" and the adjective "{cfg.adjective}", in sentences that make each meaning clear from context. Each must be used correctly, in its ordinary meaning and as that part of speech, without drawing attention to it. A word that does not fit this story is left out; a misused word is worse than a missing one.

Tone: {cfg.tone.key}: {behaviors}.
{features}
The story must be appropriate for {a} {cfg.age}-year-old {audience}."""
