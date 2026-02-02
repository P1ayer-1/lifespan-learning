CAPABILITIES = {
    "counting": False,
    "multi_step_reasoning": False,
    "perspective_taking": False,
    "planning": False,
    "abstract_reasoning": False,
    "metacognition": False,
}






def capability_constraints(tier):
    lines = []

    caps = tier["capabilities"]

    if not caps["planning"]:
        lines.append("- Do not describe plans or future steps")

    if not caps["abstract_reasoning"]:
        lines.append("- Do not explain reasons or general rules")

    if not caps["perspective_taking"]:
        lines.append("- Do not describe what other characters think or feel")

    if not caps["metacognition"]:
        lines.append("- Do not reflect on learning or growth")

    return "\n".join(lines)


def check_capability_compatibility(skill, tier):
    for cap, required in skill["requires_capabilities"].items():
        if required and not tier["capabilities"].get(cap, False):
            raise ValueError(
                f"Tier {tier['id']} lacks required capability: {cap}"
            )
