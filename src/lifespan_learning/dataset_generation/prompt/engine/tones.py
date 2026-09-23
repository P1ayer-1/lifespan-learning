# tones.py

import random


class Tone:
    def __init__(self, config: dict):
        self.key = config["key"]
        self.description = config["description"]
        self.behaviors = config["behaviors"]
        # optional tier gating (2026-09-23): a register for young children
        # should not be drawn for a grade-12 story and vice versa
        self.min_tier = config.get("min_tier", 0)
        self.max_tier = config.get("max_tier", 99)

    def is_available_for_tier(self, tier: int) -> bool:
        return self.min_tier <= tier <= self.max_tier


class ToneRegistry:
    def __init__(self, tones_config: list, rng: random.Random):
        self.tones = {config["key"]: Tone(config) for config in tones_config}
        self.rng = rng

    def available(self, banned_tones: list, tier: int | None = None) -> list[str]:
        return [
            key for key, tone in self.tones.items()
            if key not in banned_tones and (tier is None or tone.is_available_for_tier(tier))
        ]

    def get(self, banned_tones: list, tier: int | None = None) -> Tone:
        available_tones = self.available(banned_tones, tier)
        if not available_tones:
            raise ValueError(f"no tone available for tier {tier} after banning {banned_tones}")
        return self.tones[self.rng.choice(available_tones)]