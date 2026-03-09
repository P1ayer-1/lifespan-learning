
from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType
import random


class Exposure(ContentType):
    def __init__(self, config: ContentTypeConfig, rng: random.Random):
        super().__init__(config, rng=rng)

    def build_prompt(self, prompt_config: PromptConfig):

        name = prompt_config.name
        age = prompt_config.age
        goal = prompt_config.goal
        min_paragraphs = prompt_config.min_paragraphs
        max_paragraphs = prompt_config.max_paragraphs
        gender = prompt_config.gender
        location = prompt_config.location

        goal_text = f"exposes {name} to {goal}."

        tone = prompt_config.tone
        tone_label = tone.key
        tone_behaviors = "\n".join(f"- {b}" for b in tone.behaviors)

        prompt = f"""
You are a children’s short story writer. Your stories are coherent and engaging while introducing new topics to {age}-year-old children.

Write a short story ({min_paragraphs}-{max_paragraphs} paragraphs) about a {age}-year-old {gender} named {name}.
The story is set {location} and {goal_text}

Tone: {tone_label}
Tone behaviors:
{tone_behaviors}

In the story, try to use the verb "{prompt_config.verb}", the noun "{prompt_config.noun}" and the adjective "{prompt_config.adjective}" at some point.
{prompt_config.features}

Only use plain text, no markdown formatting. The story should be appropriate for a {age}-year-old child.
    """.strip()

        return prompt