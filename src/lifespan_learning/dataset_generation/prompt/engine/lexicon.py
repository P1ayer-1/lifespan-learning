

import random

from ..config_loader import load_json


class Lexicon:
    def __init__(self, lexicon_path: str, rng: random.Random):
        self.lexicon_path = lexicon_path
        self.rng = rng
        self.lexicon = load_json(self.lexicon_path)

    def sample_lexicon(self):
        """Sample a random verb, noun and adjective from the lexicon."""
        verb = self.rng.choice(self.lexicon["verbs"])
        noun = self.rng.choice(self.lexicon["nouns"])
        adjective = self.rng.choice(self.lexicon["adjectives"])
        return verb, noun, adjective