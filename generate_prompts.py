# generate_prompts.py

from prompt_builder import build_prompt
from names import get_name, GENDERS
from exposures import EXPOSURES
from tones import TONES
from tiers import TIERS
import random
import json

CONTENT_TYPES = ["exposures", "experiences", "conditioning", "skill_learning"]



def load_lexicon():
    with open('lexicon.json') as f:
        lexicon = json.load(f)
    return lexicon

FEATURES = {
    "dialogue": "include dialogue",
    "problem_and_solution": "include a problem and solution",
    "moral_or_lesson": "include a moral or lesson",
    "clear_structure": "include a clear beginning, middle, and end",
    "repetition_for_emphasis": "include repetition for emphasis",
    "sensory_details": "include sensory details",
    "humor": "include humor",
    "twist_or_surprise": "include a twist or surprise",
    "positive_message": "include a positive message",
}

def sample_features(features: dict) -> dict:
    k = random.randint(0, min(3, len(features)))
    selected_keys = random.sample(list(features.keys()), k)
    return {key: features[key] for key in selected_keys}

def save_prompts(prompts, output_path):
    with open(output_path, 'w') as f:
        json.dump(prompts, f, indent=2)

def generate_prompts(
        prompts_per_tier=10000
):
    prompts = []

    lexicon = load_lexicon()
    adjectives = lexicon["adjectives"]
    nouns = lexicon["nouns"]
    verbs = lexicon["verbs"]

    for tier in TIERS:
        for _ in range(prompts_per_tier):
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
