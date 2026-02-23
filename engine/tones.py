# tones.py

class Tone:
    def __init__(self, config: dict):
        self.tone = config["tone"]
        self.description = config["description"]