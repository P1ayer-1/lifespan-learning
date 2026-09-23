"""Knowledge domains per phase, and the optional verified fact bank.

Every prompt names one real-world domain the story should turn on (see
story_prompt.py, "Knowledge in the plot"). If a verified fact bank exists
at config/facts/phase_{id}.json, a specific fact from a domain matched to
the story's activity is injected verbatim; otherwise only the domain is
named and the model supplies the fact.

Fact bank format (written by the Lifespan repo's fact-bank builder, which
generates facts with one model and verifies them blind with another):

    {"phase": 3, "facts": [{"domain": "biology", "fact": "...", "hook": "..."}, ...]}

Domain keys are shared across phases where the topic continues, so one
content-key -> preferred-domains map serves every phase.
"""
from __future__ import annotations

import os
import random

from ..config_loader import load_json

DOMAINS = {
    0: {"animals": "animals: what they eat, where they live, how they move",
        "plants_weather": "plants, weather and the sky",
        "body": "the body and the five senses",
        "math": "counting, comparing amounts, and shapes",
        "tools": "everyday tools, materials and how things work at home",
        "people": "people's jobs and how a community works"},
    1: {"animals": "animals and their habitats and life cycles",
        "plants_weather": "plants, seasons, weather and the water cycle",
        "body": "the human body and staying healthy",
        "math": "numbers, addition, measuring and time",
        "tools": "simple machines and how everyday things work",
        "places": "maps, places and other countries",
        "history": "how people lived long ago"},
    2: {"animals": "animals, habitats and food chains",
        "plants_weather": "weather, climate, the water cycle and the Earth",
        "body": "the human body, nutrition and health",
        "math": "fractions, multiplication, measurement and simple data",
        "tools": "machines, inventions and how technology works",
        "places": "geography and cultures around the world",
        "history": "history of everyday things and famous events"},
    3: {"science": "the science behind everyday phenomena (light, sound, heat, forces)",
        "biology": "ecosystems, food webs and living things",
        "body": "body systems and health",
        "math": "ratio, percentage, probability, area and volume",
        "places": "geography, climate and cultures",
        "history": "historical events and why they happened",
        "tech": "how a technology works (engines, internet, electricity)"},
    4: {"science": "physics and chemistry ideas (energy, reactions, motion)",
        "biology": "biology, cells, genetics and evolution",
        "math": "statistics, probability and data",
        "economics": "the economics of everyday life (prices, trade-offs, interest)",
        "history": "historical events and their causes",
        "places": "geography and geology",
        "tech": "how technologies are engineered (bridges, software, batteries)"},
    5: {"science_method": "scientific method, evidence and experimental design",
        "economics": "economics and markets",
        "civics": "government, law and civic institutions",
        "psychology": "psychology and how people reason and decide",
        "history": "history and how it gets interpreted",
        "environment": "environmental systems and climate",
        "math": "mathematics as a way of reasoning (proof, modelling, exponential growth)"},
    6: {"philosophy": "philosophy of knowledge and ethics",
        "economics": "economics and public policy",
        "science_method": "science and the limits of what it can show",
        "history": "history and historiography",
        "statistics": "statistics, uncertainty and risk",
        "tech": "technology and its effects on society",
        "language": "language, mind and meaning"},
}

# content-type key -> domains that fit that activity, best first. Keys not
# listed (or with no match in the phase) fall back to a uniform draw.
CONTENT_DOMAIN_PREFS = {
    "learning_physics": ["science", "tools", "tech"], "learning_chemistry": ["science", "tools"],
    "learning_biology": ["biology", "animals", "plants_weather", "body"], "learning_history": ["history"],
    "learning_cooking": ["science", "math", "body", "tools"], "learning_to_code": ["tech", "math", "statistics"],
    "learning_music": ["science", "tools", "history", "language"], "learning_art": ["tools", "math", "history"],
    "learning_sports": ["body", "science", "math"], "learning_hygiene": ["body", "biology"],
    "learning_religious_or_cultural_practices": ["places", "history", "philosophy"],
    "playing_sports": ["body", "science", "math", "psychology"],
    "watching_sports": ["body", "science", "statistics", "psychology", "economics"],
    "playing_music": ["science", "history", "language", "tools"], "drawing_or_crafting": ["tools", "math", "science", "tech"],
    "cooking_or_baking": ["science", "math", "body"], "religious_or_cultural_events": ["places", "history", "philosophy", "civics"],
    "first_day_of_school": ["people", "psychology", "civics", "math"], "puberty": ["body", "biology", "psychology"],
    "first_date": ["psychology", "economics", "language"],
    "number_words": ["math"], "object_categories": ["animals", "tools"], "time_words": ["plants_weather", "math"],
    "social_rules": ["people", "civics", "psychology"], "colors": ["science", "plants_weather", "animals"], "shapes": ["math", "tools"],
    "emotions": ["body", "psychology", "animals"], "daily_routines": ["body"], "polite_language": ["people", "language"],
    "pretend_play": ["animals", "people", "tools"], "safety_concepts": ["body", "tools", "science"],
    "classroom_language_patterns": ["math", "people", "science"], "community_roles": ["people", "civics", "economics"],
    "simple_cause_effect": ["science", "tools", "plants_weather"], "academic_vocabulary_exposure": [],
    "group_norms": ["psychology", "people", "civics"], "media_literacy_awareness": ["psychology", "tech", "statistics"],
    "perspective_exposure": ["psychology", "history", "philosophy"], "digital_environment_patterns": ["tech", "psychology"],
    "identity_language": ["psychology", "language", "places"], "abstract_discourse_patterns": ["philosophy", "math", "science_method"],
    "civic_process_awareness": ["civics", "economics", "history"], "long_term_consequence_patterns": ["economics", "environment", "statistics"],
    "professional_communication_norms": ["economics", "language", "civics"], "ethical_framework_language": ["philosophy", "economics"],
    "systems_thinking_patterns": ["environment", "economics", "tech"],
}


class FactBank:
    """Domain and (optional) fact sampling for one phase. All draws use the
    generator's seeded rng, so prompts stay byte-identical for a seed."""

    def __init__(self, phase_id: int, rng: random.Random, facts_path: str | None = None):
        self.phase_id = phase_id
        self.rng = rng
        self.domains = DOMAINS[phase_id]
        path = facts_path or f"config/facts/phase_{phase_id}.json"
        self.facts: list[dict] = []
        if os.path.exists(path):
            data = load_json(path)
            self.facts = [f for f in data.get("facts", []) if f.get("domain") in self.domains and f.get("fact")]
        # domains that actually have facts, when a bank exists
        self._with_facts = {f["domain"] for f in self.facts}

    @property
    def has_facts(self) -> bool:
        return bool(self.facts)

    def _preferred(self, content_key: str, available: set[str]) -> list[str]:
        return [d for d in CONTENT_DOMAIN_PREFS.get(content_key, []) if d in available]

    def sample(self, content_key: str) -> tuple[str, str, str]:
        """Return (domain_description, fact, hook). fact and hook are "" when no bank exists."""
        if self.facts:
            prefs = self._preferred(content_key, self._with_facts)
            domain = prefs[0] if prefs else self.rng.choice(sorted(self._with_facts))
            pool = [f for f in self.facts if f["domain"] == domain]
            f = self.rng.choice(pool)
            return self.domains[domain], f["fact"], f.get("hook", "")
        prefs = self._preferred(content_key, set(self.domains))
        domain = prefs[0] if prefs else self.rng.choice(sorted(self.domains))
        return self.domains[domain], "", ""
