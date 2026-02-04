SCENES = {
    "object_copresence": {
        "content_type": "exposure",
        "min_tier": 0,
        "max_tier": 0,
        "required_capabilities": [],

        "entities": ["child", "child", "object"],
        "allowed_verbs": ["hold", "look", "touch"],
        "allowed_nouns": ["toy", "ball", "block"],

        "allows_change": False,
        "description": "Child holds object near another child"
    }
}
