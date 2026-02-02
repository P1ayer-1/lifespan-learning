# curriculum.py


# "capabilities": {
#     "abstract_reasoning": False, = No generalizations, theories, “why” explanations
#     "planning": False, = No future-oriented multi-step plans
#     "perspective_taking": True = Whether inner thoughts of others are allowed
# },

TIER_PROFILES = {
    0: [
        {
            "profile_id": "object_focus",
            "description": "Simple object perception and naming",

            "surface_constraints": {
                "ban_numbers": True,
                "emotion_vocab": ["happy", "sad"],
                "allowed_verbs": ["see", "hold", "touch", "look"],
                "allowed_nouns": ["ball", "toy", "cup", "block"]
            }
        },

        {
            "profile_id": "action_focus",
            "description": "Single immediate actions with objects",

            "surface_constraints": {
                "ban_numbers": True,
                "emotion_vocab": ["happy"],
                "allowed_verbs": ["pick", "drop", "open", "close"],
                "allowed_nouns": ["door", "box", "toy"]
            }
        },

        {
            "profile_id": "social_presence",
            "description": "Other people exist, but their minds do not",

            "surface_constraints": {
                "ban_numbers": True,
                "emotion_vocab": ["happy", "sad"],
                "allowed_verbs": ["see", "hold", "sit"],
                "allowed_nouns": ["mom", "dad", "child", "toy"],

                # Critical: people are objects, not minds
                "forbid_internal_states_of_others": True
            }
        }
    ]
}


TIERS = {
    0: {
        "id": 0,
        "name": "Perception and Naming",
        "approx_age": 3,
        "description": "Immediate perception, naming, and simple actions with no learning or reasoning",

        # What mental operations are possible at all
        "capabilities": {
            "learning": False,              # no improvement across attempts
            "counting": False,
            "cause_effect": False,
            "multi_step_reasoning": False,
            "perspective_taking": False,
            "planning": False,
            "abstract_reasoning": False,
            "metacognition": False
        },

        # Hard cognitive / structural limits
        "limits": {
            "max_sentences": 4,
            "max_sentence_length": 8,
            "max_entities": 2,
            "max_actions_per_sentence": 1,
            "memory_horizon": 0              # cannot refer back meaningfully
        },

        # Language-level constraints
        "language": {
            "tense": "present_only",
            "allow_dialogue": False,
            "allow_questions": False
        },

        # Strong leakage prevention
        "forbidden_words": [
            "because", "why",
            "think", "know", "realize",
            "plan", "decide",
            "before", "after", "later",
            "lesson", "means"
        ]
    }
}
