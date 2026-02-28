

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


# do we need min and max tier? since we already check that when loading the content types, maybe not? it could be useful for validation though
@dataclass
class ContentTypeConfig:
    key: str
    description: str
    locations: list[str]
    goal: str
    banned_tones: list[str]
    min_tier: int
    max_tier: int