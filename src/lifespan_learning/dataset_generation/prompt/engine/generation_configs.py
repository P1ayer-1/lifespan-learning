

# dataclass for prompt configuration
from dataclasses import asdict, dataclass
from .tones import Tone

@dataclass
class PromptConfig:
    name: str
    gender: str
    location: str
    verb: str
    noun: str
    adjective: str
    goal: str
    features: str
    tone: Tone
    grade: int
    age: int
    min_paragraphs: int
    max_paragraphs: int

    def get_metadata(self) -> dict:
        # get tone key from tone object
        tone_key = self.tone.key
        metadata = asdict(self)
        metadata["tone"] = tone_key
        return metadata

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