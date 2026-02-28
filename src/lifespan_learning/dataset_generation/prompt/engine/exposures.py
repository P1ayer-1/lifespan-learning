
from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType


class Exposure(ContentType):
    def __init__(self, config):
        super().__init__(config)

    def build_prompt(self, prompt_config: PromptConfig):
        name = prompt_config.name
        goal = prompt_config.goal

        max_paragraphs = sample_paragraph_count()

        min_paragraphs = 3
        if max_paragraphs == 6:
            min_paragraphs = 4

        if features:
            formatted_features = format_features(features)
            features_text = f"The story should {formatted_features}."
        else:
            features_text = ""

        goal_text = f"exposes {name} to {exposure_goal}."

        tone = TONES[tone_key]
        tone_label = tone["label"]
        tone_behaviors = "\n".join(f"- {b}" for b in tone["behaviors"])

        prompt = f"""
    You are a children’s short story writer. Your stories are coherent and engaging while introducing new topics to 3-year-old children.

    Write a short story ({min_paragraphs}-{max_paragraphs} paragraphs) about a 3-year-old {gender} named {name}.
    The story is set {location} and {goal_text}

    Tone: {tone_label}
    Tone behaviors:
    {tone_behaviors}

    In the story, try to use the verb "{verb}", the noun "{noun}" and the adjective "{adjective}" at some point.
    {features_text}

    Only use plain text, no markdown formatting. The story should be appropriate for a 3-year-old child.
    """.strip()

        return {
            "metadata": {
                "name": name,
                "gender": gender,
                "location": location,
                "exposure": exposure_key,
                "features": list(features.keys()),
                "verb": verb,
                "noun": noun,
                "adjective": adjective,
                "tone": tone_key,
            },
            "prompt": prompt
        }
    
