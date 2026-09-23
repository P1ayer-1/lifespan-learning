from __future__ import annotations

import random
import yaml
import json

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_list(path: str, key: str = "tiers") -> list[dict]:
    data = load_yaml(path)
    return data[key]

ARC_KINDS = ("basic_learning", "advanced_learning")


def build_arc_configs(content_type_data: dict) -> dict[str, list[dict]]:
    """One arc -> {kind: [config, ...]}.

    Two shapes are accepted. The 2026-09-23 shape puts the levels at the top
    level, each kind a LIST of grade-band levels so one subject (say
    mathematics) can carry a different concrete goal for every band:

        - key: learning_math
          description: mathematics
          basic_learning:
            - {min_tier: 0, max_tier: 1, goal: "learning to count ..."}
            - {min_tier: 2, max_tier: 3, goal: "learning to add ..."}
          advanced_learning:
            - {min_tier: 4, max_tier: 6, goal: "..."}
          locations: [...]
          banned_tones: [...]

    The original shape (levels nested under `arcs:` with one dict per kind,
    `shared_locations`, `shared_banned_tones`) still loads.
    """
    key = content_type_data["key"]
    description = content_type_data["description"]
    levels = content_type_data.get("arcs", content_type_data)
    shared_locations = content_type_data.get("shared_locations", content_type_data.get("locations", []))
    shared_banned_tones = content_type_data.get("shared_banned_tones", content_type_data.get("banned_tones", []))

    out: dict[str, list[dict]] = {kind: [] for kind in ARC_KINDS}
    for kind in ARC_KINDS:
        spec = levels.get(kind)
        if spec is None:
            continue
        for level in (spec if isinstance(spec, list) else [spec]):
            out[kind].append({
                "key": key,
                "description": description,
                **level,
                "locations": [*shared_locations, *level.get("locations", [])],
                "banned_tones": [*shared_banned_tones, *level.get("banned_tones", [])],
            })
    return out


def load_content_types(paths: list[str], allowed_content_types: list[str], tier: int, rng: random.Random) -> ContentTypeRegistry:
    allowed_content_type_data = {}

    for path in paths:
        data = load_yaml(path)

        for content_type, content_type_info in data.items():

            # Handle arcs -> basic_learning + advanced_learning
            if content_type == "arcs":
                for ct in content_type_info:
                    for kind, configs in build_arc_configs(ct).items():
                        if kind not in allowed_content_types:
                            continue
                        for config in configs:
                            if config["min_tier"] <= tier <= config["max_tier"]:
                                allowed_content_type_data.setdefault(kind, []).append(config)

            # Handle normal content types
            elif content_type in allowed_content_types:
                for ct in content_type_info:
                    if ct["min_tier"] <= tier <= ct["max_tier"]:
                        allowed_content_type_data.setdefault(content_type, []).append(ct)

    # imported here, not at module top: engine/__init__ -> phases -> tiers imports this
    # module, so a top-level import is circular when config_loader is imported first
    from lifespan_learning.dataset_generation.prompt.engine.content_type_registry import ContentTypeRegistry

    return ContentTypeRegistry(allowed_content_type_data, allowed_content_types, rng)

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

