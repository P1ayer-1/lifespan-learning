from .exposures import Exposure
from .arcs import BasicLearningArc, AdvancedLearningArc
from .experiences import Experience
from .generation_configs import ContentTypeConfig
import random
from .content_type import ContentType



class ContentTypeRegistry:
    def __init__(self, content_type_data: dict, allowed_content_types: list, rng: random.Random):
        self.allowed_content_types = allowed_content_types
        print(allowed_content_types)
        self.registry = {}
        self.rng = rng

        for content_type, configs in content_type_data.items():
            instances = []

            for config_json in configs:
                if content_type == "basic_learning":
                    config = ContentTypeConfig(**config_json)
                    instances.append(BasicLearningArc(config))

                elif content_type == "advanced_learning":
                    config = ContentTypeConfig(**config_json)
                    instances.append(AdvancedLearningArc(config))

                elif content_type == "exposures":
                    config = ContentTypeConfig(**config_json)
                    instances.append(Exposure(config))

                elif content_type == "experiences":
                    config = ContentTypeConfig(**config_json)
                    instances.append(Experience(config))

                else:
                    raise ValueError(f"Unknown content type: {content_type}")

            self.registry[content_type] = instances

    def get(self, content_type: str) -> ContentType:
        """Returns a random instance of the specified content type."""
        if content_type not in self.allowed_content_types:
            raise ValueError(f"Content type '{content_type}' is not allowed for this tier.")
        
        if content_type not in self.registry:
            raise ValueError(f"Content type '{content_type}' not found in registry.")
        
        return self.rng.choice(self.registry[content_type])