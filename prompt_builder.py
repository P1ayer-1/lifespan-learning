# prompt_builder.py
import random

TONES = [
    "The tone should be calm and simple.",
    "The tone should show curiosity.",
    "The tone should show gentle effort and learning."
]

PARAGRAPH_DISTRIBUTION = [
    (4, 0.55),
    (5, 0.35),
    (6, 0.10),
]

def sample_paragraph_count():
    values, weights = zip(*PARAGRAPH_DISTRIBUTION)
    return random.choices(values, weights, k=1)[0]



def build_prompt(name, gender, location, exposure):
    max_paragraphs = sample_paragraph_count()

    exposure_data = exposure[1]

    exposure_goal = exposure_data["exposure_goal"]

    lexicon = exposure_data["lexicon"]
    verbs = ", ".join(lexicon["verbs"])
    nouns = ", ".join(lexicon["nouns"])
    adjectives = ", ".join(lexicon["adjectives"])

    goal_text = f"exposes {name} to {exposure_goal}."     

    prompt = f"""

You are a children’s short story writer. Your stories are coherent and engaging while exposing 3 year old children to new topics.
Write a short story (3-{max_paragraphs} paragraphs) about a 3-year-old {gender} named {name}.
The story is set at {location} and {goal_text}

In the story, try to use the verb "{verbs}", the noun "{nouns}" and the adjective "{adjectives}" at some point. The story should include dialogue.

Only use plain text, no markdown formatting. The story should be appropriate for a 3-year-old child.
""".strip()

    print(prompt)

    return {
        "metadata": {
            "name": name,
            "gender": gender,
            "location": location,
            "exposure": exposure[0]
        },
        "prompt": prompt
    }  