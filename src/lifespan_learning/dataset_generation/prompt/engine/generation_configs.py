

# dataclass for prompt configuration
from dataclasses import asdict, dataclass, field
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
    framing: str
    reading_level: str
    audience_noun: str
    # 2026-09-23 template fields (story_prompt.py)
    phase: int = 0
    kind: str = "exposure"        # exposure | experience | arc
    content_key: str = ""
    domain: str = ""              # description of the knowledge domain the story turns on
    fact: str = ""                # verified fact injected verbatim, or "" when no fact bank exists
    fact_hook: str = ""
    # Names for the other people in the story ({"name", "role"} dicts, see
    # engine/names.py SideCharacterSampler); empty renders no names line.
    side_characters: list = field(default_factory=list)

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