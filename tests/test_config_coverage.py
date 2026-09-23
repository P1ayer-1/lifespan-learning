"""Configuration coverage: every draw the generator can make must be backed
by enough concrete content, and no placeholder text may reach a prompt.

Written 2026-09-23 after the audit (tools/config_audit.py) found that grades
9-12 had a single basic-learning arc ("learning to code") carrying 30-50% of
the draw, every arc goal was a "more complex X" placeholder, and tones were
all early-childhood registers with no tier gating.
"""
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

import lifespan_learning.dataset_generation.prompt as prompt_pkg
from lifespan_learning.dataset_generation.prompt.config_loader import build_arc_configs

CONFIG = Path(prompt_pkg.__file__).resolve().parent / "config"
MIN_INSTANCES = {"exposures": 8, "experiences": 8, "basic_learning": 6, "advanced_learning": 4}
MIN_TONES = 4
PLACEHOLDER = re.compile(r"more complex|more advanced|such as learning|basic concepts|at a high level", re.I)
BAD_LOCATION = re.compile(r"^at (the )?(bedroom|bathroom|kitchen|art table)$|^at mealtime$|^online$", re.I)


def load(name):
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cfg():
    tiers = load("tiers.yaml")["tiers"]
    arcs = load("content_types/arcs.yaml")["arcs"]
    arc_configs = {"basic_learning": [], "advanced_learning": []}
    for a in arcs:
        for kind, cs in build_arc_configs(a).items():
            arc_configs[kind].extend(cs)
    return {
        "tiers": tiers,
        "tones": load("tones.yaml")["tones"],
        "features": load("features.yaml")["features"],
        "exposures": load("content_types/exposures.yaml")["exposures"],
        "experiences": load("content_types/experiences.yaml")["experiences"],
        "arcs": arcs,
        **arc_configs,
    }


def _in(c, t):
    return c["min_tier"] <= t <= c["max_tier"]


def test_every_weighted_content_type_has_enough_instances_at_every_tier(cfg):
    short = []
    for t in cfg["tiers"]:
        tn = t["tier"]
        for ct in t["content_types"]:
            if ct["weight"] <= 0:
                continue
            n = sum(_in(c, tn) for c in cfg[ct["content_type"]])
            if n < MIN_INSTANCES[ct["content_type"]]:
                short.append(f"tier {tn}: {ct['content_type']} has {n} < {MIN_INSTANCES[ct['content_type']]}")
    assert not short, "\n".join(short)


def test_tier_weights_sum_to_one_and_are_not_one_placeholder_row(cfg):
    for t in cfg["tiers"]:
        assert abs(sum(c["weight"] for c in t["content_types"]) - 1.0) < 1e-6, t["tier"]
    rows = Counter(tuple(sorted((c["content_type"], c["weight"]) for c in t["content_types"])) for t in cfg["tiers"])
    assert max(rows.values()) <= 4


def test_enough_tones_survive_every_banned_list_at_every_tier(cfg):
    short = []
    for t in cfg["tiers"]:
        tn = t["tier"]
        for coll in ("exposures", "experiences", "basic_learning", "advanced_learning"):
            for c in cfg[coll]:
                if not _in(c, tn):
                    continue
                ok = [x for x in cfg["tones"] if x["key"] not in c.get("banned_tones", []) and x.get("min_tier", 0) <= tn <= x.get("max_tier", 99)]
                if len(ok) < MIN_TONES:
                    short.append(f"tier {tn} {coll}/{c['key']}: {len(ok)} tones")
    assert not short, "\n".join(short[:20])


def test_tones_are_gated_and_older_registers_exist(cfg):
    keys = {x["key"] for x in cfg["tones"]}
    assert {"wry", "reflective", "tense", "bittersweet", "matter-of-fact"} <= keys
    assert any(x.get("min_tier", 0) >= 7 for x in cfg["tones"])
    assert any(x.get("max_tier", 99) <= 6 for x in cfg["tones"])
    for x in cfg["tones"]:
        assert len(x["behaviors"]) == 3, x["key"]


def test_features_are_gated_and_never_ask_for_a_stated_moral(cfg):
    assert len(cfg["features"]) >= 15
    assert any(f.get("max_tier", 13) <= 6 for f in cfg["features"])
    assert any(f.get("min_tier", 0) >= 9 for f in cfg["features"])
    for f in cfg["features"]:
        assert not re.search(r"moral|lesson|positive message", f["instruction"], re.I), f["key"]
        assert f["instruction"][0].islower() or f["instruction"][0].isdigit(), f["key"]
    for tn in range(14):
        assert sum(f.get("min_tier", 0) <= tn <= f.get("max_tier", 13) for f in cfg["features"]) >= 5, tn


def test_no_placeholder_goals_and_goals_are_unique(cfg):
    goals = []
    for coll in ("exposures", "experiences", "basic_learning", "advanced_learning"):
        for c in cfg[coll]:
            assert not PLACEHOLDER.search(c["goal"]), f"{coll}/{c['key']}: {c['goal']!r}"
            assert 3 <= len(c["goal"].split()) <= 30, f"{coll}/{c['key']}: {c['goal']!r}"
            goals.append(c["goal"].strip().lower())
    dupes = [g for g, n in Counter(goals).items() if n > 1]
    assert not dupes, dupes[:10]


def test_locations_are_prepositional_phrases(cfg):
    bad = []
    for coll in ("exposures", "experiences", "basic_learning", "advanced_learning"):
        for c in cfg[coll]:
            assert len(c["locations"]) >= 4, f"{coll}/{c['key']}"
            for loc in c["locations"]:
                if BAD_LOCATION.match(loc) or not re.match(r"^(at|in|on|during|by|inside|outside|near|under|aboard|around|behind|backstage|onstage|along|beside)\b", loc):
                    bad.append(f"{coll}/{c['key']}: {loc!r}")
    assert not bad, "\n".join(bad[:20])


def test_arcs_cover_consecutive_bands(cfg):
    for a in cfg["arcs"]:
        for kind, cs in build_arc_configs(a).items():
            spans = sorted((c["min_tier"], c["max_tier"]) for c in cs)
            for (lo1, hi1), (lo2, hi2) in zip(spans, spans[1:]):
                assert lo2 == hi1 + 1, f"{a['key']}.{kind}: bands {spans} overlap or leave a gap"


def test_generator_runs_every_tier_with_real_config(monkeypatch):
    from lifespan_learning.dataset_generation.prompt.engine.prompt_dataset_generator import PromptDatasetGenerator

    monkeypatch.chdir(CONFIG.parent)
    gen = PromptDatasetGenerator(seed=11)
    for phase in gen.phases:
        prompts = phase.generate_prompts(len(phase.tiers) * 20)
        assert len(prompts) == len(phase.tiers) * 20
        for p in prompts:
            assert "Rules for the reply:" in p["prompt"]
            assert not PLACEHOLDER.search(p["prompt"]), p["prompt"][:200]
