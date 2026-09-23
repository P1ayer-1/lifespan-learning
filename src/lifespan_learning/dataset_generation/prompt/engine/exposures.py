from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType
from . import story_prompt
import random


class Exposure(ContentType):
    kind = "exposure"

    def __init__(self, config: ContentTypeConfig, rng: random.Random):
        super().__init__(config, rng=rng)

    def build_prompt(self, prompt_config: PromptConfig) -> str:
        return story_prompt.render(prompt_config)
