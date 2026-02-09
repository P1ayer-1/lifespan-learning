# exposures.py
TONES = {
    "curious": {
        "label": "curious",
        "behaviors": [
            "Ask gentle wondering questions",
            "Highlight noticing and discovery",
            "Express interest in how things work"
        ]
    },
    "excited": {
        "label": "excited",
        "behaviors": [
            "Use enthusiastic language",
            "Show positive anticipation",
            "Celebrate small moments"
        ]
    },
    "playful": {
        "label": "playful",
        "behaviors": [
            "Include light humor or silliness",
            "Use playful exaggeration",
            "Keep the mood fun and bouncy"
        ]
    },
    "encouraging": {
        "label": "encouraging",
        "behaviors": [
            "Praise effort rather than results",
            "Support participation",
            "Reinforce trying again"
        ]
    },
    "calm": {
        "label": "calm",
        "behaviors": [
            "Use slow, simple language",
            "Avoid urgency or conflict",
            "Maintain a soothing rhythm"
        ]
    },
    "gentle": {
        "label": "gentle",
        "behaviors": [
            "Guide softly without commands",
            "Avoid harsh corrections",
            "Use warm and careful wording"
        ]
    },
    "reassuring": {
        "label": "reassuring",
        "behaviors": [
            "Normalize feelings",
            "Emphasize safety and comfort",
            "Resolve uncertainty calmly"
        ]
    },
    "patient": {
        "label": "patient",
        "behaviors": [
            "Allow repetition of key ideas",
            "Portray mistakes as normal",
            "Respond to errors gently"
        ]
    },
    "imaginative": {
        "label": "imaginative",
        "behaviors": [
            "Include pretend or make-believe elements",
            "Let objects or ideas come alive",
            "Encourage playful imagination"
        ]
    },
    "caring": {
        "label": "caring",
        "behaviors": [
            "Show warmth and affection",
            "Use nurturing language",
            "Focus on connection and kindness"
        ]
    }
}




EXPOSURES = {

    "number_words": {
        "min_tier": 0,
        "max_tier": 0,
        "description": "rote number words", 
        "exposure_goal": "rote number words",
        "banned_tones": ["imaginative"],
        "locations": ["home", "school", "car ride"]
    },

    "object_categories": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "animals, toys, foods",
        "exposure_goal": "simple object categories such as: animals, toys and foods",
        "banned_tones": [],
        "locations": ["home", "school", "park", "car ride", "library"]
    },

    "time_words": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "yesterday, today, tomorrow",
        "exposure_goal": "basic time concepts such as yesterday, today, tomorrow, now, and later",
        "banned_tones": ["excited", "playful", "imaginative"],
        "locations": ["home", "school", "bedtime", "mealtime"]
    },

    "social_rules": {
        "min_tier": 0,
        "max_tier": 3,
        "description": "turn-taking, fairness",
        "exposure_goal": "basic social rules such as turn-taking, sharing, fairness, and following simple group rules",
        "banned_tones": ["excited", "playful"],
        "locations": ["school", "playground", "home", "daycare"]
    },

    "colors": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "basic colors",
        "exposure_goal": "basic color words such as red, blue, yellow, and green",
        "banned_tones": [],
        "locations": ["home", "school", "park", "art table"]
    },

    "shapes": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "basic shapes",
        "exposure_goal": "basic shape concepts such as circle, square, triangle, and rectangle",
        "banned_tones": ["imaginative"],
        "locations": ["home", "school", "playroom", "block area"]
    },

    "emotions": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "emotional states",
        "exposure_goal": "basic emotions such as happy, sad, angry, scared, and excited",
        "banned_tones": ["excited", "playful"],
        "locations": ["home", "school", "bedtime", "playground"]
    },

    "daily_routines": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "everyday activities",
        "exposure_goal": "common daily routines such as eating, sleeping, bathing, and getting dressed",
        "banned_tones": ["imaginative"],
        "locations": ["home", "bathroom", "bedroom", "kitchen"]
    },

    "polite_language": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "social language",
        "exposure_goal": "polite and functional phrases such as please, thank you, sorry, and asking for help",
        "banned_tones": ["playful", "excited"],
        "locations": ["home", "school", "playground", "store"]
    },

    "pretend_play": {
        "min_tier": 0,
        "max_tier": 3,
        "description": "imaginative play",
        "exposure_goal": "pretend play scenarios such as playing house, caring for toys, and role-playing simple situations",
        "banned_tones": ["calm", "patient"],
        "locations": ["playroom", "school", "home", "outdoors"]
    },

    "safety_concepts": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "basic safety awareness",
        "exposure_goal": "simple safety concepts such as hot vs cold, staying close to caregivers, and not touching dangerous objects",
        "banned_tones": ["playful", "excited", "imaginative"],
        "locations": ["home", "kitchen", "bathroom", "outdoors"]
    },
}
