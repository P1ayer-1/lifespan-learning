import random

from ..config_loader import load_list, load_json 
from lifespan_learning.dataset_generation.prompt.engine import Phase 

class PromptDatasetGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

        phase_configs = load_list("config/phases.yaml", key="phases")
        # get tier configs for each phase
        tier_configs = load_list("config/tiers.yaml", key="tiers")

        names_configs = load_json("config/names/names_gendered.json")

        self.phases: list[Phase] = []
        for phase_config, (_, name_config) in zip(phase_configs, names_configs.items()):
            tier_ids = phase_config.get("tiers", [])
            tier_config = tier_configs[tier_ids[0]:tier_ids[-1]+1]
            self.phases.append(Phase(phase_config, tier_config, name_config, rng=self.rng))
        



    def generate_prompts(self, prompts_per_phase=1000):
        all_prompts = []
        for phase in self.phases:
            print(f"Generating prompts for phase: {phase.config['name']}")

            phase_prompts = phase.generate_prompts(prompts_per_phase)
            all_prompts.extend(phase_prompts)

        return all_prompts