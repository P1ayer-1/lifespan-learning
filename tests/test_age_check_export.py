import json
from pathlib import Path

from tools.prompt_lab import age_check_export as ac


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _meta(age: int) -> dict:
    return {
        "phase": 0, "age": age, "grade": "junior kindergarten", "reading_level": "short sentences",
        "min_paragraphs": 2, "max_paragraphs": 4, "tone": "playful", "goal": "counting to five",
        "verb": "wave", "noun": "mother", "adjective": "last",
    }


def test_export_joins_target_age_and_required_words(tmp_path):
    prompts = tmp_path / "prompts.jsonl"
    stories = tmp_path / "stories.jsonl"
    out = tmp_path / "age"
    _write_jsonl(prompts, [{"prompt_hash": "h1", "metadata": _meta(3)}])
    _write_jsonl(stories, [{"prompt_hash": "h1", "phase": 0, "story": "Mia waves."}, {"prompt_hash": "orphan", "phase": 0, "story": "x"}])

    ac.export(prompts, stories, out, chunk=40)

    rows = ac.read_jsonl(out / "part0.jsonl")
    assert [r["prompt_hash"] for r in rows] == ["h1"]
    assert rows[0]["age"] == 3
    assert rows[0]["required_words"] == {"verb": "wave", "noun": "mother", "adjective": "last"}


def test_apply_queues_scores_below_threshold_without_touching_fact_queue(tmp_path):
    prompts = tmp_path / "prompts.jsonl"
    stories = tmp_path / "stories.jsonl"
    out = tmp_path / "age"
    _write_jsonl(prompts, [{"prompt_hash": "h1", "metadata": _meta(3)}, {"prompt_hash": "h2", "metadata": _meta(4)}])
    _write_jsonl(stories, [{"prompt_hash": "h1", "phase": 0, "story": "a"}, {"prompt_hash": "h2", "phase": 0, "story": "b"}])
    ac.export(prompts, stories, out, chunk=40)
    _write_jsonl(out / "part0.age.jsonl", [
        {"prompt_hash": "h1", "score": 3, "reason": ""},
        {"prompt_hash": "h2", "score": 2, "reason": "abstract theme"},
    ])

    ac.apply(stories, out)

    results = ac.read_jsonl(out / "age_check.jsonl")
    assert [(r["prompt_hash"], r["age"], r["passed"]) for r in results] == [("h1", 3, True), ("h2", 4, False)]
    queued = ac.read_jsonl(stories.with_suffix(".jsonl.age_regen_queue.jsonl"))
    assert queued == [{"prompt_hash": "h2", "phase": 0, "score": 2, "reason": "abstract theme"}]
    assert not stories.with_suffix(".jsonl.regen_queue.jsonl").exists()
    assert "pass 1/2" in (out / "report.txt").read_text(encoding="utf-8")
