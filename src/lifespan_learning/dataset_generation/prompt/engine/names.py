import json
import random
from pathlib import Path

class NameLoader:
    def __init__(self, name_config, rng: random.Random):
        self.names = name_config
        self.rng = rng

    def get_bio(self):
        """Get a random name and gender."""
        gender = self.rng.choice(["girl", "boy"])

        if gender == "girl" and self.names["Female"]:
            return self.rng.choice(self.names["Female"]), gender
        elif gender == "boy" and self.names["Male"]:
            return self.rng.choice(self.names["Male"]), gender
        else:
            raise ValueError(f"No names available for gender: {gender}")


class SideCharacterSampler:
    """Names for the people around the main character.

    The template used to name only the main character, so the generator
    invented everyone else and fell back on the same few names (pre-pilot
    phases 3/6: "Priya" in 267 and 354 of 1,000 stories, "Marcus" in 246 and
    209, "Okafor" as the teacher in 118 and 177). Each prompt now gets
    `n_peers` first names from the phase's larger name list
    (config/names/names_gendered_rank1000.json) and one adult, title plus
    surname (config/names/surnames.json).

    It draws from its own rng, not the generator's shared one, so adding
    side characters leaves every other sampled field of a prompt unchanged.
    """

    ROLE_PEER = "a friend or classmate"
    ROLE_ADULT = "an adult such as a teacher, coach or neighbour"
    TITLES = {"Female": "Ms.", "Male": "Mr."}

    def __init__(self, name_config: dict, surnames: list[str], rng: random.Random, n_peers: int = 2):
        self.names = {g: list(v) for g, v in name_config.items() if v}
        self.surnames = list(surnames)
        self.rng = rng
        self.n_peers = n_peers
        if not self.names or not self.surnames:
            raise ValueError("SideCharacterSampler needs first names and surnames")

    def sample(self, main_name: str) -> list[dict]:
        """`n_peers` peers plus one adult; no duplicates, never the main name."""
        taken = {main_name.casefold()}
        genders = sorted(self.names)
        people = []
        while len(people) < self.n_peers:
            name = self.rng.choice(self.names[self.rng.choice(genders)])
            if name.casefold() in taken:
                continue
            taken.add(name.casefold())
            people.append({"name": name, "role": self.ROLE_PEER})
        title = self.TITLES[self.rng.choice(genders)] if set(genders) == set(self.TITLES) else "Ms."
        while True:
            surname = self.rng.choice(self.surnames)
            if surname.casefold() not in taken:
                break
        people.append({"name": f"{title} {surname}", "role": self.ROLE_ADULT})
        return people


# file_path = r'config\names\top_names_unique_2021_2024.json'
# name_loader = NameLoader()
# name_loader.load_file(file_path)