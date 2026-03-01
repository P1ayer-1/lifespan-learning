# tiers.py
import json
import random
from ..config_loader import load_content_types
from .lexicon import Lexicon
from .tones import ToneRegistry
from .features import FeatureRegistry
from .generation_configs import PromptConfig

class Tier:
    def __init__(self, config: dict, tone_registry: ToneRegistry, feature_registry: FeatureRegistry, rng: random.Random):
        self.rng = rng
        self.tone_registry = tone_registry
        self.feature_registry = feature_registry

        self.tier = config["tier"]
        self.grade = config["grade"]
        self.content_types = config["content_types"]
        self.description = config["description"]
        self.age_range = config["age_range"]
        self.paragraph_distribution = config["paragraph_distribution"]
       
        self.lexicon_path = config["lexicon_path"]
        self.lexicon = Lexicon(self.lexicon_path, rng=self.rng)

        self.content_type_registry = self.load_content_types() # should be moved to phase level when we have multiple tiers per phase, but for now it's simpler to load it here since we only have one tier per phase

        

    def _weighted_sample(self, items, value_key, weight_key="weight"):
        values = [item[value_key] for item in items]
        weights = [item[weight_key] for item in items]
        return self.rng.choices(values, weights=weights, k=1)[0]

    def sample_max_paragraph_count(self):
        return self._weighted_sample(
            self.paragraph_distribution,
            value_key="paragraphs"
        )

    def sample_content_type(self):
        return self._weighted_sample(
            self.content_types,
            value_key="content_type"
        )
    
    def get_paragraph_counts(self):
        max_paragraphs = self.sample_max_paragraph_count()
        min_paragraphs = max(1, max_paragraphs - 2) # ensure at least 1 paragraph
        return min_paragraphs, max_paragraphs

    def get_content_type_paths(self):
        paths = set()
        for ct in self.content_types:
            content_type = ct["content_type"]
            if content_type in ["basic_learning", "advanced_learning"]:
                paths.add(f"config/content_types/arcs.yaml")
            else:
                paths.add(f"config/content_types/{content_type}.yaml")
        return list(paths)

    def load_content_types(self):
        # right now this leads to leads to loading the same files multiple times.
        # can fix later by loading all content types at the phase level and then filtering based on allowed content types and tier for each request
        paths = self.get_content_type_paths()
        
        return load_content_types(paths, allowed_content_types=[ct["content_type"] for ct in self.content_types], tier=self.tier, rng=self.rng)

    def generate_prompt(self, name: str, gender: str):
        # placeholder for now
        content_type_key = self.sample_content_type()
        content_type = self.content_type_registry.get(content_type_key)
        banned_tones = content_type.banned_tones
        tone = self.tone_registry.get(banned_tones)

        min_paragraphs, max_paragraphs = self.get_paragraph_counts()

        verb, noun, adjective = self.lexicon.sample_lexicon()

        features = self.feature_registry.sample_features(self.tier)
        formatted_features = self.feature_registry.format_features(features)

        age = self.rng.randint(self.age_range[0], self.age_range[1])

        prompt_config = PromptConfig(
            name=name,
            gender=gender,
            location=content_type.sample_location(), # need to add location sampling to content type base class
            verb=verb,
            noun=noun,
            adjective=adjective,
            goal=content_type.goal,
            features=formatted_features,
            tone=tone,
            grade=self.grade,
            age=age,
            min_paragraphs=min_paragraphs,
            max_paragraphs=max_paragraphs,
        )

        return content_type.build_prompt(prompt_config=prompt_config)