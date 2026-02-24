import random

class Feature:
    def __init__(self, key: str, config: dict):
        self.key = key
        self.instruction = config.get("instruction", "")
        self.min_tier = config.get("min_tier")
        self.max_tier = config.get("max_tier")
        self.weight = config.get("weight", 1.0)

    def is_available_for_tier(self, tier_number: int) -> bool:
        if self.min_tier is not None and tier_number < self.min_tier:
            return False
        if self.max_tier is not None and tier_number > self.max_tier:
            return False
        return True

    def __str__(self):
        return self.instruction
    



class FeatureRegistry:
    def __init__(self, config: dict):
        self.features = {
            key: Feature(key, value)
            for key, value in config.items()
        }

    def available_for_tier(self, tier_number: int):
        return [
            feature
            for feature in self.features.values()
            if feature.is_available_for_tier(tier_number)
        ]

    def sample_features(self, tier_number: int, max_features: int = 3) -> list[Feature]:
        available = self.available_for_tier(tier_number)

        if not available:
            return []

        k = random.randint(0, min(max_features, len(available)))

        if k == 0:
            return []

        # Weighted sampling without replacement
        selected = []
        pool = available.copy()

        for _ in range(k):
            weights = [f.weight for f in pool]
            chosen = random.choices(pool, weights=weights, k=1)[0]
            selected.append(chosen)
            pool.remove(chosen)

        return selected

    def format_features(self, features: list[Feature]) -> str:
        instructions = [f.instruction for f in features]

        if not instructions:
            return ""
        if len(instructions) == 1:
            return instructions[0]
        if len(instructions) == 2:
            return f"{instructions[0]} and {instructions[1]}"
        return ", ".join(instructions[:-1]) + ", and " + instructions[-1]