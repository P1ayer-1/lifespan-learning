from .generation_configs import PromptConfig, ContentTypeConfig


class ContentType:
    def __init__(self, config: ContentTypeConfig):
        self.key = config.key
        self.description = config.description
        self.locations = config.locations
        self.min_tier = config.min_tier
        self.max_tier = config.max_tier
        self.goal = config.goal
        self.banned_tones = config.banned_tones

    def build_prompt(self, prompt_config: PromptConfig) -> str:
        # placeholder for now, will use the prompt config to fill in the template with the appropriate details (e.g. location, tone, etc.)
        return f"Generate a {prompt_config.tone} story about {prompt_config.name} learning {self.description} at {prompt_config.location} with the goal of {self.goal}."