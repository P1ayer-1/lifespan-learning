import yaml
from engine.features import FeatureRegistry

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_tiers(path: str):
    data = load_yaml(path)
    return data["tiers"]
