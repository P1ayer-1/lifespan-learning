"""Age-check gate: a typed score question per story, following the Laya
probe pattern in D:\\Reflex\\probe\\laya_probe.py (read-only reference, not
a dependency -- Laya itself is a local classifier; this gate asks the same
*shape* of question -- one typed decision with an ordered set of labelled
levels -- but of the generation model itself, Claude Haiku 4.5, since that
is what actually wrote the stories).

For every story, asks: "is this story appropriate for a reader aged N?"
as a score over five labelled levels (0-4), forced through a strict tool
call so the answer is always one of the five integers, never free text.
Reports the pass rate per phase and queues failing prompt_hashes for
regeneration.

Levels (mirrors Laya's "score" type: an ordered list of criteria, not a
bare 1-10 guess a model tends to cluster around 7):
    0 - wildly mismatched: far too advanced or far too simple for this age,
        or content no reader of this age should see
    1 - mismatched: noticeably too advanced or too simple for this age
    2 - borderline: roughly the right age but with a clear mismatch somewhere
        (vocabulary, theme, or tone)
    3 - appropriate: a reader of this age would find this a normal, comfortable read
    4 - excellently matched: vocabulary, theme, and tone all fit this age well

PASS_THRESHOLD = 3: a story passes if a reader of the target age would find
it a normal, comfortable read or better.

Usage:
    python age_check_gate.py --stories stories.jsonl --prompts prompts.jsonl --out age_check.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, TypeVar

DEFAULT_MODEL = "claude-haiku-4-5"
PASS_THRESHOLD = 3

LEVELS = [
    "wildly mismatched: far too advanced or far too simple for this age, or content no reader of this age should see",
    "mismatched: noticeably too advanced or too simple for this age",
    "borderline: roughly the right age but with a clear mismatch somewhere (vocabulary, theme, or tone)",
    "appropriate: a reader of this age would find this a normal, comfortable read",
    "excellently matched: vocabulary, theme, and tone all fit this age well",
]

T = TypeVar("T")


def retry_call(fn: Callable[[], T], *, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0) -> T:
    """Same retryable-errors-only backoff as generate_responses.py's retry_call."""
    try:
        import anthropic
    except ImportError:
        anthropic = None

    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if anthropic is not None:
                non_retryable = (
                    anthropic.BadRequestError,
                    anthropic.AuthenticationError,
                    anthropic.PermissionDeniedError,
                    anthropic.NotFoundError,
                )
                retryable = (
                    anthropic.RateLimitError,
                    anthropic.InternalServerError,
                    anthropic.APIConnectionError,
                )
                if isinstance(exc, non_retryable):
                    raise
                if not isinstance(exc, retryable):
                    raise
            else:
                raise

            attempt += 1
            if attempt > max_retries:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            print(f"Retryable error scoring a story ({type(exc).__name__}); retrying in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)


class ScoreProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    def score(self, story: str, age: int) -> int:
        """Return an integer 0-4 (see LEVELS)."""
        ...


class AnthropicScoreProvider:
    """Forces a strict tool call so the answer is always one of the five
    integer levels -- never free text to parse."""

    TOOL = {
        "name": "score_story",
        "description": "Record the age-appropriateness score for this story.",
        "input_schema": {
            "type": "object",
            "properties": {"score": {"type": "integer", "enum": [0, 1, 2, 3, 4]}},
            "required": ["score"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    def __init__(self, model: str = DEFAULT_MODEL):
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def _prompt(self, story: str, age: int) -> str:
        levels_text = "\n".join(f"  {i}: {desc}" for i, desc in enumerate(LEVELS))
        return (
            f"Is this story appropriate for a reader aged {age}? Score it against exactly "
            f"these levels:\n{levels_text}\n\nStory:\n{story}\n\nCall score_story with your score."
        )

    def score(self, story: str, age: int) -> int:
        def call():
            return self._client.messages.create(
                model=self._model,
                max_tokens=64,
                tools=[self.TOOL],
                tool_choice={"type": "tool", "name": "score_story"},
                messages=[{"role": "user", "content": self._prompt(story, age)}],
            )

        response = retry_call(call)
        for block in response.content:
            if block.type == "tool_use" and block.name == "score_story":
                return int(block.input["score"])
        raise ValueError(f"model did not call score_story: {response.content!r}")


class FakeScoreProvider:
    """For tests: no network. `scores_by_hash` maps prompt_hash -> score (0-4)."""

    def __init__(self, model: str = "fake-model-1", scores_by_hash: dict[str, int] | None = None, default_score: int = 4):
        self._model = model
        self._scores_by_hash = scores_by_hash or {}
        self._default_score = default_score
        self.calls: list[tuple[str, int]] = []

    @property
    def model_id(self) -> str:
        return self._model

    def score(self, story: str, age: int) -> int:
        self.calls.append((story, age))
        return self._scores_by_hash.get(story, self._default_score)


@dataclass(frozen=True)
class StoryRecord:
    prompt_hash: str
    phase: int
    story: str


def load_stories(path: Path) -> list[StoryRecord]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            records.append(StoryRecord(prompt_hash=row["prompt_hash"], phase=row["phase"], story=row["story"]))
    return records


def load_prompt_ages(path: Path) -> dict[str, int]:
    ages = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ages[row["prompt_hash"]] = row["metadata"]["age"]
    return ages


def run_gate(
    stories_path: Path,
    prompts_path: Path,
    out_path: Path,
    provider: ScoreProvider,
    pass_threshold: int = PASS_THRESHOLD,
) -> dict:
    stories = load_stories(stories_path)
    ages = load_prompt_ages(prompts_path)

    results = []
    regen_queue = []
    pass_count_by_phase: dict[int, int] = {}
    total_by_phase: dict[int, int] = {}

    for record in stories:
        age = ages.get(record.prompt_hash)
        if age is None:
            continue  # story has no matching prompt in this prompts file; skip rather than guess

        score = provider.score(record.story, age)
        passed = score >= pass_threshold

        results.append(
            {
                "prompt_hash": record.prompt_hash,
                "phase": record.phase,
                "age": age,
                "score": score,
                "passed": passed,
                "model": provider.model_id,
            }
        )
        total_by_phase[record.phase] = total_by_phase.get(record.phase, 0) + 1
        if passed:
            pass_count_by_phase[record.phase] = pass_count_by_phase.get(record.phase, 0) + 1
        else:
            regen_queue.append({"prompt_hash": record.prompt_hash, "phase": record.phase, "score": score})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    regen_path = out_path.with_suffix(out_path.suffix + ".regen_queue.jsonl")
    with regen_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in regen_queue:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    pass_rate_by_phase = {
        phase: pass_count_by_phase.get(phase, 0) / total for phase, total in sorted(total_by_phase.items())
    }
    return {
        "total": len(results),
        "passed": len(results) - len(regen_queue),
        "failed": len(regen_queue),
        "pass_rate_by_phase": pass_rate_by_phase,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Age-appropriateness gate over generated stories.")
    parser.add_argument("--stories", type=Path, required=True, help="Story jsonl from generate_responses.py.")
    parser.add_argument("--prompts", type=Path, required=True, help="Prompt jsonl the stories were generated from (for target ages).")
    parser.add_argument("--out", type=Path, required=True, help="Per-story score output jsonl.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--pass-threshold", type=int, default=PASS_THRESHOLD, dest="pass_threshold")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    provider = AnthropicScoreProvider(model=args.model)
    summary = run_gate(args.stories, args.prompts, args.out, provider, args.pass_threshold)

    print(f"Scored {summary['total']} stories: {summary['passed']} passed, {summary['failed']} queued for regeneration.")
    for phase, rate in sorted(summary["pass_rate_by_phase"].items()):
        print(f"  phase {phase}: {rate * 100:.0f}% pass rate")


if __name__ == "__main__":
    main()
