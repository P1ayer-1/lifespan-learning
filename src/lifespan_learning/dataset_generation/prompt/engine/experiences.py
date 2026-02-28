from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType

class Experience(ContentType):
    def __init__(self, config):
        super().__init__(config)

    def build_prompt(self, prompt_config: PromptConfig) -> str:
        # placeholder for now, will use the prompt config to fill in the template with the appropriate details (e.g. location, tone, etc.)
        return f"Generate a {prompt_config.tone} story about {prompt_config.name} having an experience learning {self.description} at {prompt_config.location} with the goal of {self.goal}."