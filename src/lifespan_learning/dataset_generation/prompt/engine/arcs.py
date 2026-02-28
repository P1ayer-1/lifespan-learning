# arcs.py
from .generation_configs import PromptConfig, ContentTypeConfig
from .content_type import ContentType


class Arc(ContentType):
    def __init__(self, config: ContentTypeConfig):
        super().__init__(config)


class BasicLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig):
        super().__init__(config)

class AdvancedLearningArc(Arc):
    def __init__(self, config: ContentTypeConfig):
        super().__init__(config)