SKILLS = {
    "counting": {
        "description": "learning to count objects",
        "requires_capabilities": {
            "counting": True,
            "multi_step_reasoning": False,
            "abstract_reasoning": False
        },
        "surface_constraints": {
            "numbers": {
                "range": [1, 5],
                "operations": ["count"]
            }
        }
    },

    "social_interaction": {
        "description": "learning to interact with others",
        "requires_capabilities": {
            "perspective_taking": True,
            "abstract_reasoning": False
        },
        "surface_constraints": {
            "ban_numbers": True
        }
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


