

class Experience:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.description = config["description"]
        self.difficulty = config["difficulty"]