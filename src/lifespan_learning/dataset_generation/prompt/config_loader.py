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
    basic_config = shared_config.copy()
    basic_config.update(content_type_data["arcs"]["basic_learning"])
    advanced_config = shared_config.copy()
    advanced_config.update(content_type_data["arcs"]["advanced_learning"])

    basic_config["locations"] = shared_locations + basic_config.get("locations", [])
    advanced_config["locations"] = shared_locations + advanced_config.get("locations", [])

    return basic_config, advanced_config


def load_content_types(paths: list[str], allowed_content_types: list[str], tier: int) -> ContentTypeRegistry:
    allowed_content_type_data = {}
    for path in paths:
        data = load_yaml(path)
        content_type_data = {}
        for content_type, content_type_info in data.items():
            print(content_type)

            # content type could be arcs. we need to covert that to basic_learning and advanced_learning
            if content_type == "arcs":
                for ct in content_type_info:
                    basic_config, advanced_config = build_arc_configs(ct)
                    
                    # check if basic and advanced configs are allowed before checking tier
                    if "basic_learning" in allowed_content_types:
                        min_tier = basic_config["min_tier"]
                        max_tier = basic_config["max_tier"]
                        if min_tier <= tier <= max_tier:
                            content_type_data["basic_learning"] = basic_config
                    if "advanced_learning" in allowed_content_types:
                        min_tier = advanced_config["min_tier"]
                        max_tier = advanced_config["max_tier"]
                        if min_tier <= tier <= max_tier:
                            content_type_data["advanced_learning"] = advanced_config
            if content_type in allowed_content_types:
                for ct in content_type_info:
                        # print(content_type, ct)
                        min_tier = ct["min_tier"]
                        max_tier = ct["max_tier"]
                        if min_tier <= tier <= max_tier:                        
                            content_type_data[content_type] = ct
        # print(content_type_data)
        allowed_content_type_data.update(content_type_data)
    print(allowed_content_type_data)
    return ContentTypeRegistry(allowed_content_type_data, allowed_content_types)

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

