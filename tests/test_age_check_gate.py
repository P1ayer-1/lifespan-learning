"""Tests for the age-check gate. All tests use FakeScoreProvider -- no network."""
import json

from lifespan_learning.dataset_generation.quality import age_check_gate as gate


def _write_prompts(path, entries):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for prompt_hash, phase, age in entries:
            row = {"prompt_hash": prompt_hash, "prompt": "irrelevant", "metadata": {"phase": phase, "tier": 0, "age": age}}
            f.write(json.dumps(row) + "\n")


def _write_stories(path, entries):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for prompt_hash, phase, story in entries:
            row = {"prompt_hash": prompt_hash, "phase": phase, "tier": 0, "story": story, "model": "fake-model-1", "timestamp": "t"}
            f.write(json.dumps(row) + "\n")


def test_pass_rate_per_phase_and_regen_queue(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    stories_path = tmp_path / "stories.jsonl"
    out_path = tmp_path / "age_check.jsonl"

    _write_prompts(
        prompts_path,
        [("h0", 0, 5), ("h1", 0, 5), ("h2", 6, 17), ("h3", 6, 17)],
    )
    _write_stories(
        stories_path,
        [("h0", 0, "good-story"), ("h1", 0, "bad-story"), ("h2", 6, "good-story"), ("h3", 6, "good-story")],
    )

    provider = gate.FakeScoreProvider(scores_by_hash={"good-story": 4, "bad-story": 1})
    summary = gate.run_gate(stories_path, prompts_path, out_path, provider)

    assert summary["total"] == 4
    assert summary["passed"] == 3
    assert summary["failed"] == 1
    assert summary["pass_rate_by_phase"][0] == 0.5
    assert summary["pass_rate_by_phase"][6] == 1.0

    regen_path = out_path.with_suffix(out_path.suffix + ".regen_queue.jsonl")
    queued = [json.loads(l) for l in regen_path.read_text(encoding="utf-8").splitlines()]
    assert len(queued) == 1
    assert queued[0]["prompt_hash"] == "h1"


def test_pass_threshold_is_configurable(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    stories_path = tmp_path / "stories.jsonl"
    out_path = tmp_path / "age_check.jsonl"

    _write_prompts(prompts_path, [("h0", 3, 11)])
    _write_stories(stories_path, [("h0", 3, "story-scored-3")])

    provider = gate.FakeScoreProvider(scores_by_hash={"story-scored-3": 3})

    # threshold 3: passes
    summary = gate.run_gate(stories_path, prompts_path, out_path, provider, pass_threshold=3)
    assert summary["passed"] == 1

    # threshold 4: same score now fails
    summary = gate.run_gate(stories_path, prompts_path, out_path, provider, pass_threshold=4)
    assert summary["passed"] == 0
    assert summary["failed"] == 1


def test_story_without_matching_prompt_is_skipped_not_guessed(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    stories_path = tmp_path / "stories.jsonl"
    out_path = tmp_path / "age_check.jsonl"

    _write_prompts(prompts_path, [("h0", 0, 5)])
    _write_stories(stories_path, [("h0", 0, "story"), ("orphan", 0, "story with no prompt")])

    provider = gate.FakeScoreProvider(default_score=4)
    summary = gate.run_gate(stories_path, prompts_path, out_path, provider)

    assert summary["total"] == 1  # the orphan story is skipped, not scored with a guessed age
