import sys

import yaml
import json
from lifespan_learning.dataset_generation.prompt.engine.content_types import ContentTypeRegistry

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_list(path: str, key: str = "tiers") -> list[dict]:
    data = load_yaml(path)
    return data[key]

def build_arc_configs(content_type_data: dict):
    key = content_type_data["key"]
    description = content_type_data["description"]
    shared_config = {"key": key, "description": description}
    shared_locations = content_type_data.get("shared_locations", [])
    shared_config["locations"] = shared_locations
    shared_config["banned_tones"] = content_type_data.get("shared_banned_tones", [])

    basic_config = shared_config.copy()
    basic_config.update(content_type_data["arcs"]["basic_learning"])
    advanced_config = shared_config.copy()
    advanced_config.update(content_type_data["arcs"]["advanced_learning"])

    basic_config["locations"] = shared_locations + basic_config.get("locations", [])
    basic_config["banned_tones"] = shared_config["banned_tones"] + basic_config.get("banned_tones", [])
    advanced_config["locations"] = shared_locations + advanced_config.get("locations", [])
    advanced_config["banned_tones"] = shared_config["banned_tones"] + advanced_config.get("banned_tones", [])

    return basic_config, advanced_config


def load_content_types(paths: list[str], allowed_content_types: list[str], tier: int) -> ContentTypeRegistry:
    allowed_content_type_data = {}

    for path in paths:
        data = load_yaml(path)

        for content_type, content_type_info in data.items():

            # Handle arcs -> basic_learning + advanced_learning
            if content_type == "arcs":
                for ct in content_type_info:
                    basic_config, advanced_config = build_arc_configs(ct)

                    if "basic_learning" in allowed_content_types:
                        if basic_config["min_tier"] <= tier <= basic_config["max_tier"]:
                            allowed_content_type_data.setdefault("basic_learning", []).append(basic_config)

                    if "advanced_learning" in allowed_content_types:
                        if advanced_config["min_tier"] <= tier <= advanced_config["max_tier"]:
                            allowed_content_type_data.setdefault("advanced_learning", []).append(advanced_config)

            # Handle normal content types
            elif content_type in allowed_content_types:
                for ct in content_type_info:
                    if ct["min_tier"] <= tier <= ct["max_tier"]:
                        allowed_content_type_data.setdefault(content_type, []).append(ct)

    return ContentTypeRegistry(allowed_content_type_data, allowed_content_types)

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

