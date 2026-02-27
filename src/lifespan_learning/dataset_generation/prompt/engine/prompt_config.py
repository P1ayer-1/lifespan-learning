

# dataclass for prompt configuration
from dataclasses import dataclass

@dataclass
class PromptConfig:
    phase: str
    tier: str
    description: str
    name: str
    gender: str
    location: str
    verb: str
    noun: str
    adjective: str
    goal: str
    features: str
    tone: str
    min_paragraphs: int
    max_paragraphs: int