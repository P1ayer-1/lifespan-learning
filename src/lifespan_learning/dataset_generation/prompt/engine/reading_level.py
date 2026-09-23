"""Per-phase story-writer framing and reading-level instructions.

Root cause of the 2026-09-22 smoke-batch finding: the only signal a prompt
ever gave the model about reading level was the literal stated age, inside
an identical "You are a children's short story writer... appropriate for a
N-year-old child" wrapper used for every phase, JK through 12th grade. A
phase-5 story about a 15-year-old read like a phase-2 story about an
8-year-old because nothing in the prompt asked for anything else.

This module is the fix: a framing sentence and an explicit reading-level
instruction (sentence length, vocabulary register, idea complexity) per
phase, plus which noun ("child" vs "reader") belongs in the closing line.
Phases 0-2 keep a children's-story framing; phases 3-4 become middle-grade
/ young-adult fiction; phases 5-6 become older-teen/adult fiction -- never
"children's" for a reader who is 15-18.

Keyed by PHASE id (0-6), not tier id, matching phases.yaml.
"""

FRAMING_BY_PHASE = {
    0: "You write stories for young children who are just learning to understand the world.",
    1: "You write stories for children who are learning to read on their own.",
    2: "You write stories for children in the middle grades of elementary school.",
    3: "You write short fiction for middle-school readers.",
    4: "You write short fiction for early high-school readers.",
    5: "You write short fiction for older high-school readers.",
    6: "You write short fiction for readers finishing high school and starting college.",
}

READING_LEVEL_BY_PHASE = {
    0: (
        "Use very short, simple sentences (about 5-8 words each) and concrete, "
        "everyday words a young child already knows. One simple idea per sentence."
    ),
    1: (
        "Use short sentences (about 6-10 words) and simple, familiar vocabulary. "
        "An occasional two-part sentence (\"...and then...\") is fine."
    ),
    2: (
        "Mix short and medium sentences. Vocabulary can include words a 3rd-5th "
        "grader is learning. Some sentences may have two clauses."
    ),
    3: (
        "Use varied sentence length, including some compound and complex sentences. "
        "Vocabulary can include grade 6-8 level words. The story can involve simple "
        "cause-and-effect reasoning beyond the immediate scene."
    ),
    4: (
        "Use developed, varied sentence structure, including subordinate clauses. "
        "Vocabulary can include grade 9-10 level words. The story may explore a "
        "character's internal reasoning or conflicting motives."
    ),
    5: (
        "Use sophisticated sentence structure with embedded clauses and varied "
        "rhythm. Vocabulary can include grade 11 level, analytical or abstract "
        "words. The story may weigh competing perspectives or leave the outcome "
        "ambiguous."
    ),
    6: (
        "Use sophisticated, varied sentence structure and nuanced transitions "
        "between ideas. Vocabulary can include grade 12 / early-college level "
        "words. The story may engage with abstract principles or competing "
        "values and need not resolve neatly."
    ),
}

# From this phase up, the closing line says "reader," never "child."
READER_NOT_CHILD_FROM_PHASE = 4


def framing_for(phase: int) -> str:
    return FRAMING_BY_PHASE[phase]


def reading_level_for(phase: int) -> str:
    return READING_LEVEL_BY_PHASE[phase]


def audience_noun_for(phase: int) -> str:
    return "reader" if phase >= READER_NOT_CHILD_FROM_PHASE else "child"
