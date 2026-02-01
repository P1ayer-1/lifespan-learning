# arcs.py

ARCS = [
    {
        "arc_id": "counting_basic",
        "goal": "count objects correctly up to five",
        "skill": "counting",
        "story_beats": ["attempt", "mistake", "feedback", "retry"],
        "objects": ["blocks", "apples", "toys", "balls"],
        "locations": ["room", "table", "floor"],
        "min_tier": 1,
        "max_tier": 2,
    },
    {
        "arc_id": "sharing",
        "goal": "learn to share objects with another child",
        "skill": "social_interaction",
        "story_beats": ["conflict", "feedback", "adjustment"],
        "objects": ["crayons", "snacks", "toys"],
        "locations": ["school", "home", "playground"],
        "min_tier": 0,
        "max_tier": 1
    },
    {
        "arc_id": "verbs_and_nouns",
        "goal": "learn the difference between actions and things",
        "skill": "verbs_nouns",
        "story_beats": ["observe", "confusion", "example", "understanding"],
        "objects": ["ball", "dog", "cup"],
        "verbs": ["run", "jump", "hold", "throw"],
        "locations": ["yard", "room"]
    }

]
