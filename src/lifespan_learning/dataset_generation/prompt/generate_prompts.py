# generate_prompts.py
from lifespan_learning.dataset_generation.prompt.engine import PromptDatasetGenerator





if __name__ == "__main__":
    ds_generator = PromptDatasetGenerator()

    prompts = ds_generator.generate_prompts(prompts_per_phase=1000)

    print(f"Generated {len(prompts)} prompts")
    # Print a few sample prompts
    for i in range(5):
        print(prompts[i])
