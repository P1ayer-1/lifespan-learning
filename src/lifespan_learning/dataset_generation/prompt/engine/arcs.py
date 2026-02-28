# arcs.py
from .generation_configs import PromptConfig, ContentTypeConfig


class Arc:
    def __init__(self, config: dict):
        pass


class BasicLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig):
        super().__init__(config)
        self.key = config.key
        self.description = config.description
        self.locations = config.locations
        self.min_tier = config.min_tier
        self.max_tier = config.max_tier

class AdvancedLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig):
        super().__init__(config)
        self.key = config.key
        self.description = config.description
        self.locations = config.locations
        self.min_tier = config.min_tier
        self.max_tier = config.max_tier