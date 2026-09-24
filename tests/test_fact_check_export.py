import json
from pathlib import Path

from tools.prompt_lab import fact_check_export as fc


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_export_includes_context_when_no_fact_is_injected(tmp_path):
    prompts = tmp_path / "prompts.jsonl"
    stories = tmp_path / "stories.jsonl"
    out = tmp_path / "review"
    _write_jsonl(prompts, [{
        "prompt_hash": "h1",
        "metadata": {"phase": 0, "goal": "learning the five senses", "domain": "learning the five senses", "fact": ""},
    }])
    _write_jsonl(stories, [{"prompt_hash": "h1", "phase": 0, "story": "Eyes are used to see."}])

    fc.export(prompts, stories, out, chunk=40)

    row = fc.read_jsonl(out / "part0.jsonl")[0]
    assert row["activity"] == "learning the five senses"
    assert row["knowledge_domain"] == "learning the five senses"
    assert row["fact"] == ""


def test_apply_queues_false_claim_without_an_injected_fact(tmp_path):
    stories = tmp_path / "stories.jsonl"
    review = tmp_path / "review"
    review.mkdir()
    _write_jsonl(stories, [{"prompt_hash": "h1", "phase": 0, "story": "A false claim."}])
    _write_jsonl(review / "part0.verdicts.jsonl", [{
        "prompt_hash": "h1", "verdict": "adds_false_claim", "reason": "incorrect mechanism",
    }])

    fc.apply(stories, review)

    queued = fc.read_jsonl(stories.with_suffix(".jsonl.regen_queue.jsonl"))
    assert queued == [{
        "prompt_hash": "h1", "phase": 0, "verdict": "adds_false_claim", "reason": "incorrect mechanism",
    }]
