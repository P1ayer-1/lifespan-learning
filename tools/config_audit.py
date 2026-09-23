"""Audit the prompt generator's configuration for placeholders and gaps.

Reports, per tier: which content types can actually be drawn (weight > 0)
and how many concrete instances back each; which tones survive the banned
lists; which features apply; plus text-level smells (placeholder goals,
ungrammatical locations, copy-pasted location sets, unused keys).

    python tools/config_audit.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from lifespan_learning.dataset_generation.prompt.config_loader import build_arc_configs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "src" / "lifespan_learning" / "dataset_generation" / "prompt"
CONFIG = ROOT / "config"


def load(name):
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


def main() -> None:
    tiers = load("tiers.yaml")["tiers"]
    phases = load("phases.yaml")["phases"]
    tones = load("tones.yaml")["tones"]
    features = load("features.yaml")["features"]
    exposures = load("content_types/exposures.yaml")["exposures"]
    experiences = load("content_types/experiences.yaml")["experiences"]
    arcs = load("content_types/arcs.yaml")["arcs"]

    # --- instances per tier per content type ----------------------------
    def in_range(cfg, t):
        return cfg["min_tier"] <= t <= cfg["max_tier"]

    print("=== per-tier availability (instances backing each content type with weight > 0) ===")
    print("tier grade                weights                                  exposures experiences basic advanced | tones features")
    problems = []
    for t in tiers:
        tn = t["tier"]
        w = {c["content_type"]: c["weight"] for c in t["content_types"]}
        n_exp = sum(in_range(e, tn) for e in exposures)
        n_xp = sum(in_range(e, tn) for e in experiences)
        arc_cfgs = {"basic_learning": [], "advanced_learning": []}
        for a in arcs:
            for kind, cs in build_arc_configs(a).items():
                arc_cfgs[kind].extend(cs)
        n_basic = sum(in_range(c, tn) for c in arc_cfgs["basic_learning"])
        n_adv = sum(in_range(c, tn) for c in arc_cfgs["advanced_learning"])
        basic_names = sorted({c["key"] for c in arc_cfgs["basic_learning"] if in_range(c, tn)})
        # tones: banned lists differ per content type; report the minimum surviving set
        all_ct = [e for e in exposures if in_range(e, tn)] + [e for e in experiences if in_range(e, tn)]
        min_tones = min((len([x for x in tones if x["key"] not in c.get("banned_tones", [])]) for c in all_ct), default=len(tones))
        n_feat = sum(f.get("min_tier", 0) <= tn <= f.get("max_tier", 99) for f in features)
        wtxt = " ".join(f"{k[:3]}={v}" for k, v in w.items())
        print(f"{tn:>4} {t['grade']:20s} {wtxt:40s} {n_exp:>9} {n_xp:>11} {n_basic:>5} {n_adv:>8} | {min_tones:>5} {n_feat:>8}")
        for ct, n in (("exposures", n_exp), ("experiences", n_xp), ("basic_learning", n_basic), ("advanced_learning", n_adv)):
            if w.get(ct, 0) > 0 and n < 5:
                problems.append(f"tier {tn} ({t['grade']}): {ct} weight {w[ct]} but only {n} instance(s)" + (f" -> {basic_names}" if ct == "basic_learning" else ""))

    # --- weight placeholders -----------------------------------------------
    weight_sets = Counter(tuple(sorted((c["content_type"], c["weight"]) for c in t["content_types"])) for t in tiers)
    for ws, n in weight_sets.items():
        if n >= 5:
            problems.append(f"{n} tiers share the identical content-type weights {dict(ws)} (placeholder?)")

    # --- text smells -------------------------------------------------------
    placeholder_re = re.compile(r"more complex|more advanced|such as learning to|at a high level", re.I)
    bad_loc_re = re.compile(r"^at (the )?(bedroom|bathroom|kitchen|backyard|art table)$|^at mealtime$|^online$", re.I)
    for a in arcs:
        for kind, cs in build_arc_configs(a).items():
            for cfg in cs:
                if placeholder_re.search(cfg["goal"]):
                    problems.append(f"arc {a['key']}.{kind} tiers {cfg['min_tier']}-{cfg['max_tier']}: placeholder goal: {cfg['goal'][:80]!r}")
    for coll, name in ((exposures, "exposure"), (experiences, "experience")):
        for e in coll:
            bad = [l for l in e["locations"] if bad_loc_re.match(l)]
            if bad:
                problems.append(f"{name} {e['key']}: ungrammatical/odd locations {bad}")
            if e["goal"] == e["description"] and name == "experience":
                pass
    loc_sets = Counter(tuple(e["locations"]) for e in exposures + experiences)
    for ls, n in loc_sets.items():
        if n >= 4:
            problems.append(f"{n} content types share the identical location list {list(ls)[:4]}... (copy-paste?)")
    for a in arcs:
        if not (a.get("shared_banned_tones") or a.get("banned_tones")):
            problems.append(f"arc {a['key']}: no banned_tones (imaginative tone allowed on a learning arc)")

    # --- features/tones gating --------------------------------------------
    if all(f.get("min_tier", 0) == 0 and f.get("max_tier", 13) == 13 and f.get("weight", 1.0) == 1.0 for f in features):
        problems.append(f"features.yaml: all {len(features)} features apply to every tier with equal weight (no gating)")
    for f in features:
        if re.search(r"moral|lesson", f["instruction"]):
            problems.append(f"feature {f['key']}: {f['instruction']!r} contradicts the template's no-stated-lesson rule")
    if not any("min_tier" in x for x in tones):
        problems.append(f"tones.yaml: {len(tones)} tones, none gated by tier; all are early-childhood registers ({', '.join(x['key'] for x in tones)})")

    # --- phases/lexicon paths ------------------------------------------------

    # --- names -------------------------------------------------------------
    names = json.loads((CONFIG / "names" / "names_gendered.json").read_text(encoding="utf-8"))
    sizes = {k: (len(v["Male"]), len(v["Female"])) for k, v in names.items()}
    overlap = len(set(names["0"]["Male"]) & set(names["6"]["Male"]))
    print(f"\nnames per phase (male, female): {sizes}; phase 0 vs 6 male overlap {overlap}")

    print(f"\n=== {len(problems)} problems ===")
    for p in problems:
        print("-", p)


if __name__ == "__main__":
    main()
