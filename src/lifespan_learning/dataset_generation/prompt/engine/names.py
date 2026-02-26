import json
import random
from pathlib import Path

class NameLoader:
    def __init__(self):
        self.names = {
            "girls": [],
            "boys": []
        }

    def load_file(self, filepath):
        """Load names from a JSON file."""
        filepath = Path(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)


        self.names["girls"].extend(
            name.strip() for name in data.get("girls", [])
        )
        self.names["boys"].extend(
            name.strip() for name in data.get("boys", [])
        )


    def load_multiple(self, filepaths):
        """Load multiple JSON files."""
        for path in filepaths:
            self.load_file(path)

    def get_name(self, gender):
        """Get a random name by gender."""
        gender = gender.lower()

        if gender == "girl" and self.names["girls"]:
            return random.choice(self.names["girls"])
        elif gender == "boy" and self.names["boys"]:
            return random.choice(self.names["boys"])
        else:
            raise ValueError(f"No names available for gender: {gender}")

    def clear(self):
        """Clear all loaded names."""
        self.names = {"girls": [], "boys": []}


file_path = r'config\names\top_names_unique_2021_2024.json'
name_loader = NameLoader()
name_loader.load_file(file_path)