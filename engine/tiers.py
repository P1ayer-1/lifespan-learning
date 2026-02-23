# tiers.py
import json
import random

class Tier:
    def __init__(self, config: dict):
        self.tier = config["tier"]
        self.grade = config["grade"]
        self.content_types = config["content_types"]
        self.description = config["description"]
        self.age_range = config["age_range"]
        self.paragraph_distribution = config["paragraph_distribution"]
        self.lexicon_path = config["lexicon_path"]

        self.lexicon = self.load_lexicon(config["lexicon_path"])

    def sample_paragraph_count(self):
        values = [p["paragraphs"] for p in self.paragraph_distribution]
        weights = [p["weight"] for p in self.paragraph_distribution]
        return random.choices(values, weights=weights, k=1)[0]
    
    def load_lexicon(self, path):
        with open(path) as f:
            lexicon = json.load(f)
        return lexicon