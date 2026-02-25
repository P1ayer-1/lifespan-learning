# tiers.py
import json
import random
from config_loader import load_content_types

class Tier:
    def __init__(self, config: dict):
        self.tier = config["tier"]
        self.grade = config["grade"]
        self.content_types = config["content_types"]
        self.description = config["description"]
        self.age_range = config["age_range"]
        self.paragraph_distribution = config["paragraph_distribution"]
       
        self.lexicon_path = config["lexicon_path"]
        self.lexicon = self.load_lexicon()

        self.content_type_registry = self.load_content_types()

        

    def _weighted_sample(self, items, value_key, weight_key="weight"):
        values = [item[value_key] for item in items]
        weights = [item[weight_key] for item in items]
        print(random.choices(values, weights=weights, k=1)[0])
        return random.choices(values, weights=weights, k=1)[0]

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
    
    def load_lexicon(self):
        with open(self.lexicon_path) as f:
            lexicon = json.load(f)
        return lexicon
    
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
        
        return load_content_types(paths)
