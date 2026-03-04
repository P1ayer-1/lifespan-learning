from .tiers import Tier
from .names import NameLoader
from .lexicon import Lexicon

class Phase:
    def __init__(self, config, tier_configs, name_config, tone_registry, feature_registry, rng):
        self.config = config
        self.rng = rng
        self.tiers = [Tier(tier_config, tone_registry, feature_registry, rng) for tier_config in tier_configs]

        self.name_loader = NameLoader(name_config, rng)

        id = config["id"]

        self.lexicon_path = "config/lexicons/phase_{id}.json".format(id=id)
        self.lexicon = Lexicon(self.lexicon_path, rng=self.rng)

    def generate_prompts(self, prompts_per_phase):
        # Placeholder implementation - replace with actual prompt generation logic
        prompts = []

        prompts_per_tier = prompts_per_phase // len(self.tiers)
        for tier in self.tiers:
            for _ in range(prompts_per_tier):
                name, gender = self.name_loader.get_bio()
                verb, noun, adjective = self.lexicon.sample_lexicon()
                prompt = tier.generate_prompt(name=name, gender=gender, verb=verb, noun=noun, adjective=adjective)
                prompts.append(prompt)
        return prompts