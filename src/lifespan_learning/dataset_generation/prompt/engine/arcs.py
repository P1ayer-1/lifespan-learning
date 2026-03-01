# arcs.py
from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType
import random


class Arc(ContentType):
    def __init__(self, config: ContentTypeConfig, rng: random.Random):
        super().__init__(config, rng=rng)


class BasicLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig, rng: random.Random):
        super().__init__(config, rng=rng)

class AdvancedLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig, rng: random.Random):
        super().__init__(config, rng=rng)