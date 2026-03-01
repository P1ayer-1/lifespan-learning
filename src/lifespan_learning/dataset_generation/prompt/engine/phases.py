from .tiers import Tier
from .names import NameLoader
class Phase:
    def __init__(self, config, tier_configs, name_config, tone_registry, feature_registry, rng):
        self.config = config
        self.tiers = [Tier(tier_config, tone_registry, feature_registry, rng) for tier_config in tier_configs]

        self.name_loader = NameLoader(name_config, rng)

    def generate_prompts(self, prompts_per_phase):
        # Placeholder implementation - replace with actual prompt generation logic
        prompts = []

        prompts_per_tier = prompts_per_phase // len(self.tiers)
        for tier in self.tiers:
            for i in range(prompts_per_tier):
                name, gender = self.name_loader.get_bio()
                prompt = tier.generate_prompt(name=name, gender=gender)
                prompts.append(prompt)
        return prompts