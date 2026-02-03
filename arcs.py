# arcs.py

ARCS = [ # need func to check if compatible
    {
        "arc_id": "counting_basic",
        "skill": "counting",
        "skill_phase": "enumeration_small",
        "story_beats": ["conflict", "feedback", "adjustment"], # should adjust
        "goal": "count objects correctly up to five",
        "locations": ["school", "home"],
        "min_tier": 1,
        "max_tier": 2
    },

    {
        "arc_id": "sharing",
        "goal": "learn to share objects with another child",
        "skill": "social_interaction",
        "skill_phase": "co_presence",
        "story_beats": ["conflict", "feedback", "adjustment"],
        "objects": ["crayons", "snacks", "toys"],
        "locations": ["school", "home", "playground"],
        "min_tier": 0,
        "max_tier": 1
    },

]


def check_arc_compatible(tier, arc):
    min_tier = arc["min_tier"]
    max_tier = arc["max_tier"]

    if tier >= min_tier and tier <= max_tier:
        return True
    else:
        return False 