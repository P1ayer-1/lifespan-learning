# tiers.py
import json
import random
from ..config_loader import load_content_types
from .lexicon import Lexicon

class Tier:
    def __init__(self, config: dict, rng: random.Random):
        self.rng = rng

        self.tier = config["tier"]
        self.grade = config["grade"]
        self.content_types = config["content_types"]
        self.description = config["description"]
        self.age_range = config["age_range"]
        self.paragraph_distribution = config["paragraph_distribution"]
       
        self.lexicon_path = config["lexicon_path"]
        self.lexicon = Lexicon(self.lexicon_path, rng=self.rng)

        self.content_type_registry = self.load_content_types()

        

    def _weighted_sample(self, items, value_key, weight_key="weight"):
        values = [item[value_key] for item in items]
        weights = [item[weight_key] for item in items]
        return self.rng.choices(values, weights=weights, k=1)[0]

    def sample_paragraph_count(self):
        return self._weighted_sample(
            self.paragraph_distribution,
            value_key="paragraphs"
        )

    def sample_content_type(self):
        return self._weighted_sample(
            self.content_types,
            value_key="content_type"
        )
    
    def get_content_type_paths(self):
        paths = []
        for ct in self.content_types:
            content_type = ct["content_type"]
            if content_type in ["basic_learning", "advanced_learning"]:
                paths.append(f"config/content_types/arcs.yaml")
            else:
                paths.append(f"config/content_types/{content_type}.yaml")
        return paths

    def load_content_types(self):
        paths = self.get_content_type_paths()
        
        return load_content_types(paths, allowed_content_types=[ct["content_type"] for ct in self.content_types])

    def generate_prompt(self):
        # placeholder for now
        content_type_key = self.sample_content_type()
        content_type = self.content_type_registry.get(content_type_key)

        paragraph_count = self.sample_paragraph_count()

        verb, noun, adjective = self.lexicon.sample_lexicon()

        return content_type.generate_content(verb, noun, adjective, paragraph_count)