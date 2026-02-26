from config_loader import load_list
from engine.phases import Phase

class PromptDatasetGenerator:
    def __init__(self, prompts_per_phase):
        self.prompts_per_phase = prompts_per_phase

        phase_configs = load_list("config/phases.yaml", key="phases")
        # get tier configs for each phase
        tier_configs = load_list("config/tiers.yaml", key="tiers")
        phased_tier_configs = {}
        for phase in phase_configs:
            tier_ids = phase.get("tiers", [])
            phased_tier_configs[phase["id"]] = tier_configs[tier_ids[0]:tier_ids[-1]+1]
        
        
        self.phases = [Phase(config, phased_tier_configs[config["id"]]) for config in phase_configs]


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