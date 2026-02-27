from lifespan_learning.dataset_generation.prompt import load_list, load_json 
from lifespan_learning.dataset_generation.prompt.engine import Phase 

class PromptDatasetGenerator:
    def __init__(self, prompts_per_phase):
        self.prompts_per_phase = prompts_per_phase

        phase_configs = load_list("config/phases.yaml", key="phases")
        # get tier configs for each phase
        tier_configs = load_list("config/tiers.yaml", key="tiers")

        names_configs = load_json("config/names/names_gendered.json")

        self.phases = []
        for phase_config, name_config in zip(phase_configs, names_configs):
            tier_ids = phase_config.get("tiers", [])
            tier_config = tier_configs[tier_ids[0]:tier_ids[-1]+1]
            self.phases.append(Phase(phase_config, tier_config, name_config))
        



    def generate_prompts(self):
        all_prompts = []
        for phase in self.phases:
            print(f"Generating prompts for phase: {phase.config['name']}")
            # print(f"Phase config: {phase.config}")
            # print(f"Phase content types: {phase.config['content_types']}")
            # print(f"Phase features: {phase.config['features']}")
            # print(f"Phase exposures: {phase.config['exposures']}")
            # print(f"Phase experiences: {phase.config['experiences']}")
            # print(f"Phase tones: {phase.config['tones']}")

            phase_prompts = phase.generate_prompts(self.prompts_per_phase)
            all_prompts.extend(phase_prompts)

        return all_prompts