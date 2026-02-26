


class ContentTypeRegistry:
    def __init__(self, allowed_content_types: list):
        self.allowed_content_types = allowed_content_types

        self.experiences = []
        self.exposures = []
        self.basic_learning = []
        self.advanced_learning = []