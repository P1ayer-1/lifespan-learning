# prompt_builder.py
import random

TONES = [
    "The tone should be calm and simple.",
    "The tone should show curiosity.",
    "The tone should show gentle effort and learning."
]

PARAGRAPH_DISTRIBUTION = [
    ("two", 0.55),
    ("three", 0.35),
    ("four", 0.10),
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

    goal_text = f"GOAL:\nExpose {name} to {exposure_goal}.\n"     

    prompt = f"""
You are generating a short, simple story about a 3-year-old {gender} named {name}. The story is set at {location}.

{goal_text}


CONSTRAINTS: 
- One to {max_paragraphs} paragraphs total 
- Present tense only 
- Use at least one verb: {verbs}
- Use at least one noun: {nouns}
- Use at least one adjective: {adjectives}

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