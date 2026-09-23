import json
import random

from ..config_loader import load_list, load_json 
from .tones import ToneRegistry
from .features import FeatureRegistry
from lifespan_learning.dataset_generation.prompt.engine import Phase 

class PromptDatasetGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

        tones_config = load_list("config/tones.yaml", key="tones")
        self.tone_registry = ToneRegistry(tones_config, rng=self.rng)

        features_config = load_list("config/features.yaml", key="features")
        self.feature_registry = FeatureRegistry(features_config, rng=self.rng)

        phase_configs = load_list("config/phases.yaml", key="phases")
        # get tier configs for each phase
        tier_configs = load_list("config/tiers.yaml", key="tiers")

        names_configs = load_json("config/names/names_gendered.json")
        tiers_by_id = {tier_config["tier"]: tier_config for tier_config in tier_configs}

        self.phases: list[Phase] = []
        for phase_config in phase_configs:
            phase_id = phase_config["id"]
            tier_ids = phase_config.get("tiers", [])
            missing_tiers = [tier_id for tier_id in tier_ids if tier_id not in tiers_by_id]
            if missing_tiers:
                raise ValueError(f"phase {phase_id} references unknown tier ids: {missing_tiers}")
            name_config = names_configs.get(str(phase_id))
            if name_config is None:
                raise ValueError(f"missing names config for phase {phase_id}")
            phase_tiers = [tiers_by_id[tier_id] for tier_id in tier_ids]
            self.phases.append(Phase(phase_config, phase_tiers, name_config, tone_registry=self.tone_registry, feature_registry=self.feature_registry, rng=self.rng))
        



    def generate_prompts(self, prompts_per_phase=1000):
        all_prompts = []
        for phase in self.phases:
            print(f"Generating prompts for phase: {phase.config['name']}")

            phase_prompts = phase.generate_prompts(prompts_per_phase)
            all_prompts.extend(phase_prompts)

        return all_prompts
    

    def save_prompts(self, prompts: list[dict], filename: str):
        """Save generated prompts and metadata to a jsonl file"""
        with open(filename, "w") as f:
            for prompt in prompts:
                f.write(json.dumps(prompt) + "\n")
