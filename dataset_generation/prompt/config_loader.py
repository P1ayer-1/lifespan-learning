import yaml
from engine.features import FeatureRegistry
from engine.content_types import ContentTypeRegistry

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_list(path: str, key: str = "tiers") -> list[dict]:
    data = load_yaml(path)
    return data[key]

def load_content_types(paths: list[str]) -> ContentTypeRegistry:
    content_type_data = {}
    for path in paths:
        data = load_yaml(path)
        content_type_data.update(data)
    return ContentTypeRegistry(content_type_data)


# features = load_yaml("config/content_types/arcs.yaml")

# print(features)