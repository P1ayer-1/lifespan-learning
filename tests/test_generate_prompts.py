"""Tests for generate_prompts.py.

No test setup existed in this repo before this change, so these are plain
pytest tests with no special fixtures beyond pytest's own `tmp_path` and
`monkeypatch`. No network access is used anywhere in this file.
"""
import json
import sys
from pathlib import Path

import pytest

import lifespan_learning.dataset_generation.prompt as prompt_pkg
from lifespan_learning.dataset_generation.prompt import generate_prompts as gp

PROMPT_DIR = Path(prompt_pkg.__file__).resolve().parent


@pytest.fixture(autouse=True)
def _cwd_in_prompt_dir(monkeypatch):
    # PromptDatasetGenerator's config loaders resolve paths like
    # "config/phases.yaml" relative to the current working directory; this
    # is pre-existing behaviour, not something these tests change.
    monkeypatch.chdir(PROMPT_DIR)


def _generate(split, seed, phases, per_phase, tiers=None):
    argv = [
        "--split", split,
        "--seed", str(seed),
        "--per-phase", str(per_phase),
        "--out", "unused.jsonl",
    ]
    if phases is not None:
        argv.extend(["--phases", phases])
    if tiers is not None:
        argv.extend(["--tiers", tiers])
    args = gp.build_arg_parser().parse_args(argv)
    return gp.generate(args)


def test_determinism_same_seed_same_prompts():
    """Same seed and config -> byte-identical prompts (Rule: 'Seeded and recorded')."""
    records_a = _generate("train", seed=42, phases="0,3", per_phase=8)
    records_b = _generate("train", seed=42, phases="0,3", per_phase=8)

    dump_a = [json.dumps(r, sort_keys=True) for r in records_a]
    dump_b = [json.dumps(r, sort_keys=True) for r in records_b]
    assert dump_a == dump_b
    assert len(records_a) > 0


def test_different_seed_different_prompts():
    records_a = _generate("train", seed=42, phases="0", per_phase=8)
    records_b = _generate("train", seed=43, phases="0", per_phase=8)
    hashes_a = {r["prompt_hash"] for r in records_a}
    hashes_b = {r["prompt_hash"] for r in records_b}
    assert hashes_a.isdisjoint(hashes_b)


def test_every_record_carries_split_phase_tier_and_hash():
    records = _generate("exam", seed=7, phases="0", per_phase=4)
    assert records
    for record in records:
        assert record["metadata"]["split"] == "exam"
        assert record["metadata"]["phase"] == 0
        assert isinstance(record["metadata"]["tier"], int)
        assert len(record["prompt_hash"]) == 64  # sha256 hex


def test_unknown_phase_id_rejected():
    with pytest.raises(SystemExit):
        _generate("train", seed=1, phases="999", per_phase=1)


def test_non_divisible_per_phase_count_is_exact_and_balanced():
    records = _generate("train", seed=1, phases="2", per_phase=5)
    assert len(records) == 5
    counts = {tier: sum(r["metadata"]["tier"] == tier for r in records) for tier in (4, 5, 6)}
    assert counts == {4: 2, 5: 2, 6: 1}


def test_tier_filter_generates_only_requested_tiers_with_exact_phase_counts():
    records = _generate("train", seed=1, phases=None, tiers="5,7,9", per_phase=5)
    assert len(records) == 10
    assert {r["metadata"]["tier"] for r in records} == {5, 7, 9}
    assert sum(r["metadata"]["phase"] == 2 for r in records) == 5
    assert sum(r["metadata"]["phase"] == 3 for r in records) == 5
    phase_3_counts = {
        tier: sum(r["metadata"]["tier"] == tier for r in records)
        for tier in (7, 9)
    }
    assert phase_3_counts == {7: 3, 9: 2}


def test_unknown_tier_id_rejected():
    with pytest.raises(SystemExit, match="Unknown tier"):
        _generate("train", seed=1, phases="0", tiers="999", per_phase=1)


def test_tier_outside_requested_phases_rejected():
    with pytest.raises(SystemExit, match="outside the requested phases"):
        _generate("train", seed=1, phases="0", tiers="4", per_phase=1)


def test_split_refusal_is_a_hard_exit(tmp_path, capsys):
    """The refusal that protects the whole experiment's validity: an --out
    that already holds train data must reject an exam run (and vice versa),
    with a hard, non-zero exit -- never a silent overwrite."""
    out_path = tmp_path / "prompts.jsonl"

    train_argv = [
        "--split", "train", "--seed", "1", "--phases", "0",
        "--per-phase", "2", "--out", str(out_path),
    ]
    gp.main(train_argv)
    assert out_path.exists()
    original_content = out_path.read_text(encoding="utf-8")

    exam_argv = [
        "--split", "exam", "--seed", "2", "--phases", "0",
        "--per-phase", "2", "--out", str(out_path),
    ]
    with pytest.raises(SystemExit) as excinfo:
        gp.main(exam_argv)
    assert excinfo.value.code == 1

    # File must be untouched by the refused run.
    assert out_path.read_text(encoding="utf-8") == original_content

    err = capsys.readouterr().err
    assert "REFUSING" in err


def test_same_split_rerun_is_allowed(tmp_path):
    """Regenerating/resuming the SAME split at the same --out is not refused."""
    out_path = tmp_path / "prompts.jsonl"
    argv = [
        "--split", "train", "--seed", "1", "--phases", "0",
        "--per-phase", "2", "--out", str(out_path),
    ]
    gp.main(argv)
    # Should not raise.
    gp.main(argv)
    assert out_path.exists()


def test_sidecar_written_next_to_output(tmp_path):
    out_path = tmp_path / "prompts.jsonl"
    argv = [
        "--split", "train", "--seed", "1", "--phases", "0",
        "--per-phase", "4", "--out", str(out_path),
    ]
    gp.main(argv)
    sidecar_path = tmp_path / "prompts.jsonl.sidecar.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["split"] == "train"
    assert sidecar["seed"] == 1
    assert sidecar["total_prompts"] > 0
    assert sidecar["counts_per_tier"] == {"0": 2, "1": 2}


# --------------------------------------------------------------------------
# 2026-09-23 template (engine/story_prompt.py, engine/facts.py)
# --------------------------------------------------------------------------
from lifespan_learning.dataset_generation.prompt.engine import story_prompt, facts as facts_mod


def test_every_prompt_uses_the_shared_template():
    records = _generate("train", seed=3, phases="0,3,6", per_phase=6)
    assert records
    for r in records:
        p, m = r["prompt"], r["metadata"]
        assert p.startswith("Rules for the reply:")
        assert "No title" in p and "no markdown" in p
        assert f'the verb "{m["verb"]}"' in p and f'the noun "{m["noun"]}"' in p and f'the adjective "{m["adjective"]}"' in p
        assert "Thinking the story shows:" in p
        assert "Knowledge in the plot:" in p
        assert m["domain"]  # a knowledge domain is always chosen and recorded
        if m["fact"]:  # a verified fact from config/facts is injected verbatim
            assert f'this real fact: "{m["fact"]}"' in p
        else:  # no fact bank for the phase: the prompt names the domain instead
            assert m["domain"] in p
        assert m["kind"] in ("exposure", "experience", "arc")
        assert m["content_key"]
        if m["phase"] >= 4:
            assert p.rstrip().endswith("reader.")
        else:
            assert p.rstrip().endswith("child.")


def test_article_before_age():
    assert story_prompt.article(8) == "an"
    assert story_prompt.article(11) == "an"
    assert story_prompt.article(18) == "an"
    assert story_prompt.article(5) == "a"
    assert story_prompt.article(16) == "a"


def test_fact_bank_injects_verified_fact_matched_to_activity(tmp_path):
    import random
    bank_path = tmp_path / "phase_3.json"
    bank_path.write_text(json.dumps({"phase": 3, "facts": [
        {"domain": "biology", "fact": "Monarch caterpillars eat only milkweed.", "hook": "a garden with no milkweed"},
        {"domain": "history", "fact": "The printing press reached Europe in the 1450s.", "hook": "a copied book"},
    ]}), encoding="utf-8")
    bank = facts_mod.FactBank(3, rng=random.Random(0), facts_path=str(bank_path))
    assert bank.has_facts
    # learning_biology prefers the biology domain
    domain, fact, hook = bank.sample("learning_biology")
    assert fact == "Monarch caterpillars eat only milkweed."
    assert hook == "a garden with no milkweed"
    assert domain == facts_mod.DOMAINS[3]["biology"]
    # learning_history prefers history
    _, fact, _ = bank.sample("learning_history")
    assert fact.startswith("The printing press")


def test_fact_bank_without_file_names_a_domain_only(tmp_path):
    import random
    bank = facts_mod.FactBank(5, rng=random.Random(0), facts_path=str(tmp_path / "missing.json"))
    assert not bank.has_facts
    domain, fact, hook = bank.sample("learning_to_code")
    assert fact == "" and hook == ""
    assert domain in facts_mod.DOMAINS[5].values()


def test_fact_bank_uses_activity_to_choose_a_directly_related_fact(tmp_path):
    import random
    bank_path = tmp_path / "phase_0.json"
    bank_path.write_text(json.dumps({"phase": 0, "facts": [
        {"domain": "math", "fact": "A square has four equal sides.", "hook": "sorting square and round crackers"},
        {"domain": "math", "fact": "The last number counted tells how many objects there are.", "hook": "counting blocks twice"},
    ]}), encoding="utf-8")
    bank = facts_mod.FactBank(0, rng=random.Random(0), facts_path=str(bank_path))

    _, fact, _ = bank.sample("learning_math", "to count a group of objects and explain how many there are")

    assert fact.startswith("The last number counted")


def test_fact_bank_omits_unrelated_fact_instead_of_forcing_domain_match(tmp_path):
    import random
    bank_path = tmp_path / "phase_0.json"
    bank_path.write_text(json.dumps({"phase": 0, "facts": [
        {"domain": "tools", "fact": "Bread dough rises because yeast makes gas.", "hook": "watching dough grow"},
        {"domain": "math", "fact": "A triangle has three straight sides.", "hook": "sorting crackers"},
    ]}), encoding="utf-8")
    bank = facts_mod.FactBank(0, rng=random.Random(0), facts_path=str(bank_path))
    activity = "the idea that printed words carry meaning and books are read front to back"

    domain, fact, hook = bank.sample("print_concepts", activity)

    assert (domain, fact, hook) == (activity, "", "")


def test_fact_match_does_not_count_connectives_as_relevance(tmp_path):
    import random
    bank_path = tmp_path / "phase_0.json"
    bank_path.write_text(json.dumps({"phase": 0, "facts": [
        {"domain": "body", "fact": "Hair and fingernails keep growing.", "hook": "a child scared of a haircut"},
    ]}), encoding="utf-8")
    bank = facts_mod.FactBank(0, rng=random.Random(0), facts_path=str(bank_path))
    activity = "basic emotions such as happy, sad, angry, scared and excited"

    domain, fact, hook = bank.sample("emotions", activity)

    assert (domain, fact, hook) == (activity, "", "")


def test_render_with_and_without_fact():
    from lifespan_learning.dataset_generation.prompt.engine.tones import Tone
    from lifespan_learning.dataset_generation.prompt.engine.generation_configs import PromptConfig
    from lifespan_learning.dataset_generation.prompt.engine import reading_level

    tone = Tone({"key": "curious", "description": "", "behaviors": ["Ask gentle wondering questions"]})
    base = dict(name="Mia", gender="girl", location="at home", verb="measure", noun="shadow", adjective="sticky",
                goal="cooking or baking", features="include dialogue", tone=tone, grade="6th grade", age=11,
                min_paragraphs=3, max_paragraphs=5, framing=reading_level.framing_for(3),
                reading_level=reading_level.reading_level_for(3), audience_noun="child",
                phase=3, kind="experience", content_key="cooking_or_baking", domain="ratio, percentage, probability, area and volume")
    without = story_prompt.render(PromptConfig(**base))
    assert "one accurate, real-world idea about ratio, percentage" in without
    assert "an 11-year-old girl named Mia" in without
    with_fact = story_prompt.render(PromptConfig(**base, fact="Doubling a recipe doubles every ingredient.", fact_hook="a cake for twice the guests"))
    assert 'this real fact: "Doubling a recipe doubles every ingredient."' in with_fact
    assert "a cake for twice the guests" in with_fact
    assert "Keep the fact accurate as stated" in with_fact
    # older phases carry the scene rule and reader assumption; phase 0 does not
    assert "No paragraph is pure reflection" in with_fact
    base0 = {**base, "phase": 0, "age": 4, "framing": reading_level.framing_for(0), "reading_level": reading_level.reading_level_for(0)}
    p0 = story_prompt.render(PromptConfig(**base0))
    assert "No paragraph is pure reflection" not in p0 and "Assume the reader" not in p0
