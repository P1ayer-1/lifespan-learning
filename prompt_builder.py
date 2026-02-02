# prompt_builder.py

import random
from typing import Dict
from curriculum import TIERS, TIER_PROFILES
from skills import SKILLS, build_skill_constraints
from capabilities import check_capability_compatibility

NAMES = ["Sam", "Alex", "Mia", "Leo", "Ava", "Noah", "Olivia"]

TONES = [
    "The tone should be calm and simple.",
    "The tone should show curiosity.",
    "The tone should show gentle effort and learning."
]


def format_story_beats(beats):
    return "\n".join(
        f"{i + 1}. {beat.upper()}" for i, beat in enumerate(beats)
    )


def build_prompt(tier_id, arc, seed):

    rng = random.Random(seed)

    tier = TIERS[tier_id]
    profile = rng.choice(TIER_PROFILES[tier_id])

    # Validate skill compatibility
    check_capability_compatibility(
        SKILLS[arc["skill"]],
        tier
    )

    # Merge constraints
    constraints = merge_constraints(
        tier,
        profile,
        SKILLS[arc["skill"]]
    )



# def build_prompt(tier, arc, seed):
#     rng = random.Random(seed)
#     skill = SKILLS[arc["skill"]]

#     name = rng.choice(NAMES)
#     location = rng.choice(arc["locations"])

#     skill_constraints = build_skill_constraints(skill, arc)

#     prompt_text = f"""
# You are generating a short story for a machine learning dataset.

# GOAL:
# Show a child learning to {arc["goal"]}.

# STRUCTURE:
# Write the story using the following stages in order:
# {format_story_beats(arc["story_beats"])}

# CONSTRAINTS:
# - Maximum {tier["max_sentences"]} sentences total
# - Maximum {tier["max_sentence_length"]} words per sentence
# - Use age-appropriate, concrete language
# - Do not explain lessons directly
# {skill_constraints}

# CONTENT:
# - Main character: {name}
# - Location: {location}

# IMPORTANT:
# Show confusion, awkwardness, or uncertainty before improvement.
# End with emotional or practical understanding.
# """.strip() # not sure if important thing should always be the same

#     return {
#         "prompt": prompt_text,
#         "metadata": {
#             "tier": tier["id"],
#             "arc": arc["arc_id"],
#             "skill": arc["skill"],
#             "seed": seed
#         }
#     }
