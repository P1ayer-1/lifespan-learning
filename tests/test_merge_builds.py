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
