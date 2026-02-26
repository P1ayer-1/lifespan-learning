# generate_prompts.py

import sys

from prompt_builder import build_prompt
# from names import get_name, GENDERS
# from exposures import EXPOSURES
# from tones import TONES
from engine.tiers import Tier

from config_loader import load_content_types
import random
from engine.prompt_dataset_generator import PromptDatasetGenerator





if __name__ == "__main__":
    ds_generator = PromptDatasetGenerator(prompts_per_phase=1000)

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
    # print("\nRANDOM PROMPTS:\n")
    # for _ in range(5):
    #     random_prompt = random.choice(prompts)
    #     print(random_prompt["prompt"])
    #     print("\n---\n")

    # # Save to file
    # save_prompts(prompts, 'generated_prompts.json')
