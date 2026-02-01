# curriculum.py


# "capabilities": {
#     "abstract_reasoning": False, = No generalizations, theories, “why” explanations
#     "planning": False, = No future-oriented multi-step plans
#     "perspective_taking": True = Whether inner thoughts of others are allowed
# },




TIERS = [
    {
        "id": 0,
        "name": "Objects and Naming",
        "max_sentences": 4,
        "max_sentence_length": 8,
        "numbers_allowed": [1, 2, 3],
        "forbidden_words": ["because", "think", "plan", "before", "after"],
        "description": "simple observation and labeling"
    },
    {
        "id": 1,
        "name": "Counting and Categories",
        "max_sentences": 5,
        "max_sentence_length": 10,
        "numbers_allowed": [1, 2, 3, 4, 5],
        "forbidden_words": ["because", "decide", "remember"],
        "description": "basic counting with mistakes and correction"
    },
    {
        "id": 2,
        "name": "Cause and Effect",
        "max_sentences": 6,
        "max_sentence_length": 12,
        "numbers_allowed": [1, 2, 3, 4, 5],
        "forbidden_words": ["abstract", "theory", "strategy"],
        "description": "simple cause and effect with feedback"
    }
    ,
    {
        "id": 3,
        "name": "Early Social Understanding", # seems like this should be in lower teir
        "max_sentences": 6,
        "max_sentence_length": 14,
        "capabilities": {
            "abstract_reasoning": False,
            "planning": False,
            "perspective_taking": True
        },
        "forbidden_words": ["theory", "strategy", "always", "never"]
    }
]
