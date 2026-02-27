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
            return random.choice(self.names["Female"]), gender
        elif gender == "boy" and self.names["Male"]:
            return random.choice(self.names["Male"]), gender
        else:
            raise ValueError(f"No names available for gender: {gender}")


# file_path = r'config\names\top_names_unique_2021_2024.json'
# name_loader = NameLoader()
# name_loader.load_file(file_path)