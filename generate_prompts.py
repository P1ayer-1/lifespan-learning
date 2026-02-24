# generate_prompts.py

import sys

from prompt_builder import build_prompt
# from names import get_name, GENDERS
# from exposures import EXPOSURES
# from tones import TONES
from engine.tiers import Tier

from config_loader import load_tiers
import random
import json
import yaml

CONTENT_TYPES = ["exposures", "experiences", "basic_learning", "advanced_learning"] # need to add sampling



def save_prompts(prompts, output_path):
    with open(output_path, 'w') as f:
        json.dump(prompts, f, indent=2)

def read_yaml(path):
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return data

def generate_prompts(
        prompts_per_tier=10000
):
    prompts = []

    # lexicon = read_yaml("config/config/lexicons/tier_0.yaml")
    # print(f"Loaded lexicon with {len(lexicon['adjectives'])} adjectives, {len(lexicon['nouns'])} nouns, and {len(lexicon['verbs'])} verbs.")
    # adjectives = lexicon["adjectives"]
    # nouns = lexicon["nouns"]
    # verbs = lexicon["verbs"]

    tiers = load_tiers("config/tiers.yaml")


    for tier_config in tiers:
        print(tier_config)
        tier = Tier(tier_config)
        for _ in range(prompts_per_tier):
            # weighted sampling of content type based on tier configuration
            content_type = tier.sample_content_type()

            print(f"Sampled content type: {content_type}")
            sys.exit(0)
            
            exposure_key = random.choice(list(EXPOSURES.keys()))
            exposure = EXPOSURES[exposure_key]
            location = random.choice(exposure["locations"])
            gender = random.choice(GENDERS)
            verb = random.choice(verbs)
            noun = random.choice(nouns)
            adjective = random.choice(adjectives)
            name = get_name(gender)
            features = sample_features(FEATURES)
            tone_key = random.choice([k for k in TONES.keys() if k not in exposure["banned_tones"]])     
            result = build_exposure_prompt(name, gender, location, exposure, exposure_key, features, verb, noun, adjective, tone_key)
            prompts.append(result)
    return prompts


if __name__ == "__main__":
    prompts = generate_prompts()

    print(f"Generated {len(prompts)} prompts.")

    # # Print example
    # example = prompts[0]
    # # print("METADATA:", example["metadata"])
    # print("\nPROMPT:\n")
    # print(example["prompt"])

    # # calculate average prompt length
    # total_length = sum(len(p["prompt"]) for p in prompts)
    # average_length = total_length / len(prompts)
    # print(f"\nAverage prompt length: {average_length:.2f} characters.")

    # # find the longest prompt
    # longest_prompt = max(prompts, key=lambda p: len(p["prompt"]))
    # print(f"\nLongest prompt length: {len(longest_prompt['prompt'])} characters.")
    # print("\nLongest prompt:\n")
    # print(longest_prompt["prompt"])

    # print 5 random prompts
    print("\nRANDOM PROMPTS:\n")
    for _ in range(5):
        random_prompt = random.choice(prompts)
        print(random_prompt["prompt"])
        print("\n---\n")

    # Save to file
    save_prompts(prompts, 'generated_prompts.json')
