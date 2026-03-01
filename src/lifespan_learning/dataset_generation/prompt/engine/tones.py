# tones.py

import random


class Tone: # should this be a dataclass?
    def __init__(self, config: dict):
        self.key = config["key"]
        self.description = config["description"]
        self.behaviors = config["behaviors"]


class ToneRegistry:
    def __init__(self, tones_config: list, rng: random.Random):
        self.tones = {config["key"]: Tone(config) for config in tones_config}
        self.rng = rng

    def get(self, banned_tones: list) -> Tone:
        available_tones = [tone for tone in self.tones.keys() if tone not in banned_tones]
        if not available_tones:
            return None  # maybe raise an exception
        selected_tone = self.rng.choice(available_tones)
        return self.tones[selected_tone]