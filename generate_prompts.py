# generate_prompts.py

from curriculum import TIERS
from arcs import ARCS
from prompt_builder import build_prompt




def generate_prompts(
    prompts_per_arc: int = 5,
    base_seed: int = 42
):
    prompts = []
    seed = base_seed

    for tier in TIERS:
        for arc in ARCS:
            for _ in range(prompts_per_arc):
                result = build_prompt(tier, arc, seed)
                prompts.append(result)
                seed += 1

    return prompts


if __name__ == "__main__":
    prompts = generate_prompts(prompts_per_arc=3)

    # Print example
    example = prompts[0]
    print("METADATA:", example["metadata"])
    print("\nPROMPT:\n")
    print(example["prompt"])
