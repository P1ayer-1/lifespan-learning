import json

from tools.prompt_lab import merge_builds as mb


def _fact(key: str, fact: str) -> dict:
    return {"content_key": key, "fact": fact, "hook": "old hook"}


def _setup(tmp_path, verdicts: list[dict] | None) -> None:
    (tmp_path / "revisions.json").write_text(json.dumps({
        "retire": [{"content_key": "time_words", "fact": "A week has seven days."},
                   {"content_key": "colors", "fact": "Not in the bank."}],
        "reword": [{"content_key": "sports", "from": "Old soccer fact.", "fact": "New soccer fact.", "hook": "new hook"}],
    }), encoding="utf-8")
    if verdicts is not None:
        (tmp_path / "_verify").mkdir()
        (tmp_path / "_verify" / "revisions.json").write_text(json.dumps(verdicts), encoding="utf-8")


def test_revisions_retire_and_swap_in_verified_rewording(tmp_path):
    _setup(tmp_path, [{"i": 0, "verdict": "true", "reason": ""}])
    keep = [_fact("time_words", "A week has seven days."), _fact("calendar_words", "A week has seven days."),
            _fact("sports", "Old soccer fact."), _fact("colors", "Red is a color.")]
    lines: list[str] = []
    out = mb._apply_revisions(keep, tmp_path, lines)
    # retirement is per activity: the same text under another activity stays
    assert out == [_fact("calendar_words", "A week has seven days."),
                   {"content_key": "sports", "fact": "New soccer fact.", "hook": "new hook"},
                   _fact("colors", "Red is a color.")]
    assert "'retired': 1" in lines[0] and "'reworded': 1" in lines[0]
    assert "not found: [('colors', 'Not in the bank.')]" in lines[0]


def test_unverified_rewording_drops_the_old_fact_without_shipping_the_new(tmp_path):
    for verdicts in (None, [{"i": 0, "verdict": "false", "reason": "too vague"}]):
        case = tmp_path / str(verdicts is None)
        case.mkdir()
        _setup(case, verdicts)
        out = mb._apply_revisions([_fact("sports", "Old soccer fact.")], case, [])
        assert out == []


def test_no_revisions_file_leaves_facts_unchanged(tmp_path):
    keep = [_fact("colors", "Red is a color.")]
    assert mb._apply_revisions(keep, tmp_path, []) == keep


def test_merge_activity_facts_is_phase_parameterized(tmp_path):
    """Phase N != 0 reads _gen{N}/_verify{N} against phase_{N}_activities.json
    and writes into phase_{N}.json alongside its existing domain facts,
    without touching phase_0's directories or output."""
    facts_dir = tmp_path
    act_dir = facts_dir / "activity"
    (act_dir / "_gen3").mkdir(parents=True)
    (act_dir / "_verify3").mkdir(parents=True)

    (act_dir / "phase_3_activities.json").write_text(json.dumps({
        "phase": 3,
        "activities": [{"content_key": "learning_physics", "kind": "arc",
                         "activity": "band goal", "tiers": [7], "example_settings": []}],
    }), encoding="utf-8")

    (act_dir / "_gen3" / "part0.json").write_text(json.dumps({
        "part": 0,
        "facts": [{"content_key": "learning_physics", "fact": "Sound needs a medium.", "hook": "h"},
                   {"content_key": "learning_physics", "fact": "Unverified filler.", "hook": "h"},
                   {"content_key": "not_an_activity", "fact": "Off-list, must be dropped.", "hook": "h"}],
    }), encoding="utf-8")
    (act_dir / "_verify3" / "part0.json").write_text(json.dumps([
        {"i": 0, "verdict": "true", "reason": ""},
        {"i": 1, "verdict": "false", "reason": "vague"},
        {"i": 2, "verdict": "true", "reason": ""},
    ]), encoding="utf-8")

    # existing domain-level bank, as installed from config/facts/phase_3.json
    (facts_dir / "phase_3.json").write_text(json.dumps({
        "phase": 3, "facts": [{"domain": "science", "fact": "A domain fact.", "hook": "h"}],
    }), encoding="utf-8")

    mb.merge_activity_facts(phase=3, base_dir=facts_dir)

    result = json.loads((facts_dir / "phase_3.json").read_text(encoding="utf-8"))
    assert {"domain": "science", "fact": "A domain fact.", "hook": "h"} in result["facts"]
    assert {"content_key": "learning_physics", "fact": "Sound needs a medium.", "hook": "h"} in result["facts"]
    assert not any(f.get("fact") == "Off-list, must be dropped." for f in result["facts"])
    assert len(result["facts"]) == 2
    assert (act_dir / "summary3.txt").exists()
    # phase 0's own directories/output are untouched by a phase-3 merge
    assert not (act_dir / "_gen").exists()
    assert not (facts_dir / "phase_0.json").exists()
