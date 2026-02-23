# arcs.py


class Arc:
    def __init__(self, config: dict):
        self.key = config["key"]
        self.description = config["description"]
        self.arcs = config["arcs"]
        self.shared_locations = config["shared_locations"]

    def is_valid_for_tier(self, arc_type: str, tier: int) -> bool:
        bounds = self.arcs[arc_type]
        return bounds["min_tier"] <= tier <= bounds["max_tier"]