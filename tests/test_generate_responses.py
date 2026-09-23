"""Tests for the batch response generator (response/generate_responses.py).

All tests use FakeBatchProvider -- no network access anywhere in this file.

Every gr.run()/gr.main() call passes an explicit registry_path/--corpus-registry
scoped to the test's own tmp_path. The default registry location is one
directory ABOVE --out (see default_registry_path), and pytest's tmp_path
fixture often shares that grandparent directory across tests in the same
session -- relying on the default here would leak a model id between
unrelated tests.
"""
import json

import pytest

from lifespan_learning.dataset_generation.response import generate_responses as gr
from lifespan_learning.dataset_generation.response.providers import (
    BatchResultItem,
    FakeBatchProvider,
)


def _write_prompts(path, n, phase=3, tier=7):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for i in range(n):
            row = {
                "prompt_hash": f"hash-{i:03d}",
                "prompt": f"Write a story number {i}.",
                "metadata": {"phase": phase, "tier": tier, "split": "train"},
            }
            f.write(json.dumps(row) + "\n")


def _registry(tmp_path):
    return tmp_path / "_registry.json"


def test_generation_writes_frozen_shape(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 5)

    fake = FakeBatchProvider(model="claude-haiku-4-5")
    summary = gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 5
    assert summary["skipped"] == 0
    assert summary["failed"] == 0

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    for line in lines:
        record = json.loads(line)
        assert set(record.keys()) == {"prompt_hash", "phase", "tier", "story", "model", "timestamp"}
        assert record["model"] == "claude-haiku-4-5"
        assert record["phase"] == 3
        assert record["tier"] == 7


def test_resume_skips_already_written_hashes(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 5)

    fake = FakeBatchProvider(model="claude-haiku-4-5")
    gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    # A second run with a provider that fails if asked to submit anything new
    # proves resume works: nothing should be missing, so submit_batch is
    # never called (a killed-then-rerun invocation costs nothing extra).
    class ExplodingProvider(FakeBatchProvider):
        def submit_batch(self, items, max_tokens):
            raise AssertionError("should not submit a batch when everything is already resumed")

    exploding = ExplodingProvider(model="claude-haiku-4-5")
    summary = gr.run(prompts_path, out_path, fake_provider=exploding, registry_path=_registry(tmp_path))

    assert summary["written"] == 0
    assert summary["skipped"] == 5
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5  # no duplicates


def test_limit_only_submits_up_to_limit(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 10)

    fake = FakeBatchProvider(model="claude-haiku-4-5")
    summary = gr.run(prompts_path, out_path, limit=3, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 3
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_model_mismatch_is_a_hard_refusal(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 2)

    fake_a = FakeBatchProvider(model="model-a")
    gr.run(prompts_path, out_path, fake_provider=fake_a, registry_path=_registry(tmp_path))

    fake_b = FakeBatchProvider(model="model-b")
    with pytest.raises(SystemExit) as excinfo:
        gr.run(prompts_path, out_path, fake_provider=fake_b, registry_path=_registry(tmp_path))
    assert excinfo.value.code == 1


def test_model_mismatch_across_phase_files_in_same_directory(tmp_path, capsys):
    """The auditor's exact scenario: a directory holding train_phase_3.jsonl
    on one model, and a request to write train_phase_4.jsonl on another,
    must exit non-zero and the message must name both files and both
    models -- even though train_phase_4.jsonl itself doesn't exist yet."""
    prompts_path = tmp_path / "prompts.jsonl"
    _write_prompts(prompts_path, 2, phase=3)

    phase3_path = tmp_path / "train_phase_3.jsonl"
    fake_haiku = FakeBatchProvider(model="claude-haiku-4-5")
    gr.run(prompts_path, phase3_path, fake_provider=fake_haiku, registry_path=_registry(tmp_path))

    phase4_prompts = tmp_path / "phase4_prompts.jsonl"
    _write_prompts(phase4_prompts, 2, phase=4)
    phase4_path = tmp_path / "train_phase_4.jsonl"
    fake_other_model = FakeBatchProvider(model="claude-sonnet-9")

    with pytest.raises(SystemExit) as excinfo:
        gr.run(phase4_prompts, phase4_path, fake_provider=fake_other_model, registry_path=_registry(tmp_path))
    assert excinfo.value.code == 1

    err = capsys.readouterr().err
    assert "train_phase_3.jsonl" in err
    assert "train_phase_4.jsonl" in err
    assert "claude-haiku-4-5" in err
    assert "claude-sonnet-9" in err
    assert "Use a different --out" not in err  # must never suggest routing around it as a fix
    assert "NOT fixed by writing to a different --out" in err
    assert not phase4_path.exists()  # refused before any request was submitted


def test_model_mismatch_across_splits_via_registry(tmp_path, capsys):
    """A train/ and exam/ directory sharing a corpus root: exam must carry
    the same model id as train, caught via the shared registry file even
    though the two splits are different directories with no files in common."""
    corpus_root = tmp_path / "corpus"
    train_dir = corpus_root / "train"
    exam_dir = corpus_root / "exam"
    train_dir.mkdir(parents=True)
    exam_dir.mkdir(parents=True)

    train_prompts = train_dir / "prompts.jsonl"
    _write_prompts(train_prompts, 2, phase=0)
    train_out = train_dir / "train_phase_0.jsonl"
    gr.run(train_prompts, train_out, fake_provider=FakeBatchProvider(model="claude-haiku-4-5"))

    exam_prompts = exam_dir / "prompts.jsonl"
    _write_prompts(exam_prompts, 2, phase=0)
    exam_out = exam_dir / "exam_phase_0.jsonl"

    with pytest.raises(SystemExit) as excinfo:
        gr.run(exam_prompts, exam_out, fake_provider=FakeBatchProvider(model="claude-sonnet-9"))
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "claude-haiku-4-5" in err
    assert "claude-sonnet-9" in err
    assert not exam_out.exists()

    # The matching model is allowed straight through.
    gr.run(exam_prompts, exam_out, fake_provider=FakeBatchProvider(model="claude-haiku-4-5"))
    assert exam_out.exists()


def test_non_retryable_error_goes_to_failed_file_and_is_not_retried(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 2)

    results = {
        "hash-000": BatchResultItem(
            custom_id="hash-000", outcome="errored", retryable=False, error_message="invalid_request: bad prompt"
        ),
    }
    fake = FakeBatchProvider(model="claude-haiku-4-5", results_by_custom_id=results)
    summary = gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 1  # hash-001 still succeeds
    failed_path = out_path.with_suffix(out_path.suffix + ".failed.jsonl")
    assert failed_path.exists()
    failures = [json.loads(l) for l in failed_path.read_text(encoding="utf-8").splitlines()]
    assert any(f["prompt_hash"] == "hash-000" for f in failures)

    # A pending batch_state carrying it forward for retry must NOT exist.
    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "hash-000" not in state.get("pending_retry_hashes", [])


def test_retryable_error_is_queued_not_dropped(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 2)

    results = {
        "hash-000": BatchResultItem(
            custom_id="hash-000", outcome="errored", retryable=True, error_message="truncated at max_tokens"
        ),
    }
    fake = FakeBatchProvider(model="claude-haiku-4-5", results_by_custom_id=results)
    summary = gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 1
    failed_path = out_path.with_suffix(out_path.suffix + ".failed.jsonl")
    if failed_path.exists():
        failures = [json.loads(l) for l in failed_path.read_text(encoding="utf-8").splitlines()]
        assert not any(f["prompt_hash"] == "hash-000" for f in failures)

    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "hash-000" in state["pending_retry_hashes"]


def test_resume_with_pending_retries_and_no_batch_id_submits_fresh_batch(tmp_path):
    """Reproduces the 2026-09-22 smoke-batch bug: a state file with
    batch_id=None and pending_retry_hashes must NOT try to poll/retrieve a
    None batch id (providers.py raised ValueError: "Expected a non-empty
    value for message_batch_id but received None") -- it must submit a
    fresh batch for those hashes instead."""
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 4)

    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    gr.save_batch_state(
        state_path,
        {
            "batch_id": None,
            "custom_ids": [],
            "pending_retry_hashes": ["hash-000", "hash-001", "hash-002", "hash-003"],
            "retry_attempt": 1,
        },
    )

    fake = FakeBatchProvider(model="claude-haiku-4-5")
    summary = gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 4
    assert len(fake.submitted_batches) == 1
    submitted_ids = {item.custom_id for batch in fake.submitted_batches.values() for item in batch}
    assert submitted_ids == {"hash-000", "hash-001", "hash-002", "hash-003"}
    assert not state_path.exists()  # fully resolved -> state cleared, not left dangling


def test_model_scan_ignores_openrouter_cache_sidecar(tmp_path):
    """A resumed OpenRouter run scans sibling JSONL files for model ids.
    Its own cache contains batch/result records rather than corpus records and
    must not be parsed as stories (which would raise KeyError: prompt_hash).
    """
    out_path = tmp_path / "stories.jsonl"
    out_path.write_text(
        json.dumps({
            "prompt_hash": "hash-000",
            "phase": 0,
            "tier": 0,
            "story": "A story.",
            "model": "model-a",
            "timestamp": "t",
        }) + "\n",
        encoding="utf-8",
    )
    cache_path = tmp_path / "stories.jsonl.openrouter_cache.jsonl"
    cache_path.write_text(
        json.dumps({"batch_id": "batch-1", "custom_ids": ["hash-000"]}) + "\n",
        encoding="utf-8",
    )

    assert gr.model_ids_in_directory(tmp_path) == {"stories.jsonl": "model-a"}


def test_pending_retry_that_still_fails_updates_state_without_crashing(tmp_path):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 2)

    state_path = out_path.with_suffix(out_path.suffix + ".batch_state.json")
    gr.save_batch_state(
        state_path,
        {"batch_id": None, "custom_ids": [], "pending_retry_hashes": ["hash-000"], "retry_attempt": 1},
    )

    results = {
        "hash-000": BatchResultItem(custom_id="hash-000", outcome="errored", retryable=True, error_message="truncated at max_tokens"),
    }
    fake = FakeBatchProvider(model="claude-haiku-4-5", results_by_custom_id=results)
    summary = gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))

    assert summary["written"] == 0
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending_retry_hashes"] == ["hash-000"]
    assert state["retry_attempt"] == 2  # bumped from 1


def test_unhandled_failure_exits_nonzero(tmp_path, monkeypatch):
    """The exact defect the smoke batch found: a crash inside run() must
    never exit 0 -- a failure that reports success is undetectable
    downstream. main() must translate ANY unhandled exception into a
    non-zero exit."""
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 1)

    class ExplodingProvider:
        model_id = "claude-haiku-4-5"

        def submit_batch(self, items, max_tokens):
            raise ValueError("Expected a non-empty value for message_batch_id but received None")

    monkeypatch.setattr(gr, "build_provider", lambda model, fake: ExplodingProvider())

    with pytest.raises(SystemExit) as excinfo:
        gr.main(
            [
                "--prompts", str(prompts_path), "--out", str(out_path),
                "--corpus-registry", str(_registry(tmp_path)),
            ]
        )
    assert excinfo.value.code == 1


def test_dry_run_makes_no_provider_call_and_prints_estimate(tmp_path, capsys, monkeypatch):
    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 100)

    def explode():
        raise AssertionError("dry-run must not construct a real provider / call the API")

    monkeypatch.setattr(gr, "build_provider", lambda *a, **k: explode())

    gr.main(["--prompts", str(prompts_path), "--out", str(out_path), "--dry-run"])
    captured = capsys.readouterr()
    assert "Dry run: 100 requests" in captured.out
    assert "estimated cost, Batch API" in captured.out
    assert not out_path.exists()


# --------------------------------------------------------------------------
# clean_story: the deterministic backstop against titles and markdown
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("# The Big Day\n\nMia woke up early. It was her birthday.", "Mia woke up early. It was her birthday."),
        ("The Big Day\n\nMia woke up early. It was her birthday.", "Mia woke up early. It was her birthday."),
        ("THE PHILOSOPHY OF VOLLEYBALL\n\nSofia sat down.", "Sofia sat down."),
        # a real first sentence is kept even when short
        ("Mia woke up.\n\nIt was her birthday.", "Mia woke up.\n\nIt was her birthday."),
        # a one-line story is never emptied
        ("Short story", "Short story"),
        # emphasis markers go, words stay
        ("Mia said **no**. She __meant__ it.", "Mia said no. She meant it."),
        ("  \nMia woke up early.\n\n", "Mia woke up early."),
    ],
)
def test_clean_story(raw, expected):
    assert gr.clean_story(raw) == expected


def test_generation_strips_titles_from_written_stories(tmp_path):
    from lifespan_learning.dataset_generation.response.providers import BatchResultItem

    prompts_path = tmp_path / "prompts.jsonl"
    out_path = tmp_path / "stories.jsonl"
    _write_prompts(prompts_path, 1)
    fake = FakeBatchProvider(
        model="claude-haiku-4-5",
        results_by_custom_id={"hash-000": BatchResultItem(custom_id="hash-000", outcome="succeeded", text="# A Title\n\nThe story.")},
    )
    gr.run(prompts_path, out_path, fake_provider=fake, registry_path=_registry(tmp_path))
    record = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["story"] == "The story."
