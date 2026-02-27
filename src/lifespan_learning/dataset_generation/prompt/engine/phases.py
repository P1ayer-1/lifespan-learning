from .tiers import Tier
from .names import NameLoader
class Phase:
    def __init__(self, config, tier_configs, name_config, rng):
        self.config = config
        self.tiers = [Tier(tier_config, rng) for tier_config in tier_configs]

        self.name_loader = NameLoader(name_config, rng)
    
    def generate_prompts(self, prompts_per_phase):
        # Placeholder implementation - replace with actual prompt generation logic
        prompts = []

        prompts_per_tier = prompts_per_phase // len(self.tiers)
        for tier in self.tiers:
            for i in range(prompts_per_tier):
                prompt = f"Prompt {i+1} for tier '{tier.tier}' in phase '{self.config['name']}'"
                prompts.append({"prompt": prompt, "phase": self.config['name'], "tier": tier.tier})
        return prompts