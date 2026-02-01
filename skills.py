SKILLS = {
    "counting": { # should do multiplication, divison, subtraction
        "allow_numbers": [1, 2, 3, 4, 5], # should do random numbers. or atleast random starting number. should do addition w more than just one number at a time (ex. 10, 20, 30)
        "require_numbers": True
    },
    
    "verbs_nouns": {
        "allow_numbers": False,
        "grammar_focus": ["verbs", "nouns"], 
        "ban_numbers": True
    },
    "social_interaction": {
        "allow_numbers": False,
        "emotion_words_allowed": True,
        "ban_numbers": True
    }
}



def build_skill_constraints(skill_spec, arc):
    lines = []

    if skill_spec.get("ban_numbers"):
        lines.append("- Do not use numbers or counting")

    if "allow_numbers" in skill_spec and skill_spec["allow_numbers"]:
        lines.append(f"- Only use these numbers if needed: {skill_spec['allow_numbers']}")

    if skill_spec.get("grammar_focus"):
        focus = ", ".join(skill_spec["grammar_focus"])
        lines.append(f"- Focus on using clear {focus}")

    if skill_spec.get("emotion_words_allowed"):
        emotions = ", ".join(arc.get("emotions", []))
        if emotions:
            lines.append(f"- Emotion words allowed: {emotions}")

    return "\n".join(lines)
