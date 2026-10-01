from .tiers import Tier
from .names import NameLoader, SideCharacterSampler
from .lexicon import Lexicon
from .facts import FactBank

class Phase:
    def __init__(self, config, tier_configs, name_config, tone_registry, feature_registry, rng,
                 side_sampler: SideCharacterSampler | None = None):
        self.config = config
        self.rng = rng
        id = config["id"]
        # Knowledge domains for this phase, plus the verified fact bank when
        # config/facts/phase_{id}.json exists (see engine/facts.py).
        self.fact_bank = FactBank(id, rng=rng)
        self.tiers = [
            Tier(tier_config, tone_registry, feature_registry, rng, phase_id=id, fact_bank=self.fact_bank) for tier_config in tier_configs
        ]

        self.name_loader = NameLoader(name_config, rng)
        # Own rng (see SideCharacterSampler), so the shared schedule is untouched.
        self.side_sampler = side_sampler

        self.lexicon_path = "config/lexicons/phase_{id}.json".format(id=id)
        self.lexicon = Lexicon(self.lexicon_path, rng=self.rng)

    def generate_prompts(self, prompts_per_phase, tier_ids=None):
        """Generate exactly ``prompts_per_phase`` prompts across selected tiers.

        Counts are balanced deterministically: each tier receives the quotient,
        and the first ``remainder`` tiers receive one additional prompt.
        """
        prompts = []

        selected_tiers = self.tiers
        if tier_ids is not None:
            wanted = set(tier_ids)
            selected_tiers = [tier for tier in self.tiers if tier.tier in wanted]
        if not selected_tiers:
            return prompts

        prompts_per_tier, remainder = divmod(prompts_per_phase, len(selected_tiers))
        for index, tier in enumerate(selected_tiers):
            tier_count = prompts_per_tier + (1 if index < remainder else 0)
            for _ in range(tier_count):
                name, gender = self.name_loader.get_bio()
                verb, noun, adjective = self.lexicon.sample_lexicon()
                side = self.side_sampler.sample(name) if self.side_sampler else None
                prompt = tier.generate_prompt(name=name, gender=gender, verb=verb, noun=noun, adjective=adjective,
                                              side_characters=side)
                prompt["metadata"]["phase"] = self.config["id"]
                prompts.append(prompt)
        return prompts
