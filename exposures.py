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
        "locations": [
            "at home", "at school", "during a car ride", "at the library",
            "in a playroom", "at mealtime", "at the playground", "at daycare",
            "at the store", "at grandparent's house"
        ]
    },

    "object_categories": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "animals, toys, foods",
        "exposure_goal": "simple object categories such as: animals, toys and foods",
        "banned_tones": [],
        "locations": [
            "at home", "at school", "at the park", "during a car ride", "at the library",
            "at the store", "in a playroom", "at mealtime", "at daycare", "outdoors"
        ]
    },

    "time_words": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "yesterday, today, tomorrow",
        "exposure_goal": "basic time concepts such as yesterday, today, tomorrow, now, and later",
        "banned_tones": ["excited", "playful", "imaginative"],
        "locations": [
            "at home", "at school", "at bedtime", "at mealtime",
            "at daycare", "during a car ride", "at the bedroom",
            "at the park", "at the library", "at the store"
        ]
    },

    "social_rules": {
        "min_tier": 0,
        "max_tier": 3,
        "description": "turn-taking, fairness",
        "exposure_goal": "basic social rules such as turn-taking, sharing, fairness, and following simple group rules",
        "banned_tones": ["excited", "playful"],
        "locations": [
            "at school", "at the playground", "at home", "at daycare",
            "in a playroom", "at the park", "at the library", "at the store",
            "at mealtime", "at grandparent's house"
        ]
    },

    "colors": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "basic colors",
        "exposure_goal": "basic color words such as red, blue, yellow, and green",
        "banned_tones": [],
        "locations": [
            "at home", "at school", "at the park", "at the art table",
            "in a playroom", "at the store", "outdoors", "at daycare",
            "at grandparent's house", "at art class"
        ]
    },

    "shapes": {
        "min_tier": 0,
        "max_tier": 1,
        "description": "basic shapes",
        "exposure_goal": "basic shape concepts such as circle, square, triangle, and rectangle",
        "banned_tones": ["imaginative"],
        "locations": [
            "at home", "at school", "in a playroom",
            "at the art table", "at the library", "at daycare",
            "at art class"
        ]
    },

    "emotions": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "emotional states",
        "exposure_goal": "basic emotions such as happy, sad, angry, scared, and excited",
        "banned_tones": ["excited", "playful"],
        "locations": [
            "at home", "at school", "at bedtime", "at the playground",
            "at daycare", "at the park", "at mealtime", "at the bedroom",
            "at the library", "at the store"
        ]
    },

    "daily_routines": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "everyday activities",
        "exposure_goal": "common daily routines such as eating, sleeping, bathing, and getting dressed",
        "banned_tones": ["imaginative"],
        "locations": [
            "at home", "at the bathroom", "at the bedroom", "at the kitchen",
            "at mealtime", "at bedtime", "at daycare", "at grandparent's house",
            "at school", "at school pickup"
        ]
    },

    "polite_language": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "social language",
        "exposure_goal": "polite and functional phrases such as please, thank you, sorry, and asking for help",
        "banned_tones": ["playful", "excited"],
        "locations": [
            "at home", "at school", "at the playground", "at the store",
            "at the library", "at daycare", "at the park", "at mealtime",
            "at grandparent's house", "during a car ride"
        ]
    },

    "pretend_play": {
        "min_tier": 0,
        "max_tier": 3,
        "description": "imaginative play",
        "exposure_goal": "pretend play scenarios such as playing house, caring for toys, and role-playing simple situations",
        "banned_tones": ["calm", "patient"],
        "locations": [
            "in a playroom", "at school", "at home", "outdoors",
            "at the park", "at daycare", "at the playground",
            "at grandparent's house", "at a friend's house", "in a forest"
        ]
    },

    "safety_concepts": {
        "min_tier": 0,
        "max_tier": 2,
        "description": "basic safety awareness",
        "exposure_goal": "simple safety concepts such as hot vs cold, staying close to caregivers, and not touching dangerous objects",
        "banned_tones": ["playful", "excited", "imaginative"],
        "locations": [
            "at home", "at the kitchen", "at the bathroom", "outdoors",
            "at the playground", "at the park", "during a car ride", "at the store"
        ]
    },
}
