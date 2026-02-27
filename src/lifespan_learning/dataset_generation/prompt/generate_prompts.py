# generate_prompts.py
from lifespan_learning.dataset_generation.prompt.engine import PromptDatasetGenerator





if __name__ == "__main__":
    ds_generator = PromptDatasetGenerator(prompts_per_phase=1000)
