"""A/B story generation harness for prompt-template experiments.

Builds prompts with the repo's PromptDatasetGenerator (baseline) and with a
candidate template that consumes the SAME sampled configuration (same seed,
same rng draws), so every pair differs only in the prompt wording. Sends
both to Claude Haiku 4.5 (the production generation model) in parallel and
writes one jsonl per variant with the story, stop_reason and usage.

Usage (from anywhere; the script chdirs to the prompt/ directory itself):
    python gen_ab.py --variants baseline,v1 --n-per-phase 3 --seed 1 --out runs/r1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROMPT_DIR = REPO / "src" / "lifespan_learning" / "dataset_generation" / "prompt"
ENV_FILE = REPO.parent / "Lifespan" / ".env"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 2500


def load_env() -> None:
    if "ANTHROPIC_API_KEY" in os.environ:
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Capture the sampled configuration of every prompt, independent of template.
# ---------------------------------------------------------------------------
def build_configs(seed: int, n_per_phase: int, phases: list[int]) -> list[dict]:
    """Run the real generator once and record, per prompt, the PromptConfig
    plus the content-type kind, by intercepting build_prompt on each class."""
    os.chdir(PROMPT_DIR)
    sys.path.insert(0, str(PROMPT_DIR.parents[3]))  # src/
    from lifespan_learning.dataset_generation.prompt.engine import exposures, experiences, arcs
    from lifespan_learning.dataset_generation.prompt.engine.prompt_dataset_generator import PromptDatasetGenerator

    captured: list[dict] = []
    # Hook the Arc base class so BOTH basic_learning and advanced_learning are
    # captured. Rounds r1-r3 hooked only BasicLearningArc, so every prompt
    # after an advanced_learning draw within a phase had its metadata (age,
    # grade, target words) shifted by one row; phase ids were unaffected, so
    # the band-guess numbers stand, but per-story age targets for those rows
    # were off by a row.
    originals = {
        "exposure": exposures.Exposure.build_prompt,
        "experience": experiences.Experience.build_prompt,
        "arc": arcs.Arc.build_prompt,
    }

    def make_hook(kind, original):
        def hook(self, prompt_config):
            text = original(self, prompt_config)
            captured.append({"kind": kind, "content_key": self.key, "baseline_prompt": text, "cfg": prompt_config})
            return text
        return hook

    exposures.Exposure.build_prompt = make_hook("exposure", originals["exposure"])
    experiences.Experience.build_prompt = make_hook("experience", originals["experience"])
    arcs.Arc.build_prompt = make_hook("arc", originals["arc"])

    gen = PromptDatasetGenerator(seed=seed)
    out = []
    for phase in gen.phases:
        pid = phase.config["id"]
        if pid not in phases:
            continue
        captured.clear()
        # generate_prompts splits per tier; ask for enough that every tier gets >= 1
        n_tiers = len(phase.tiers)
        want = n_per_phase * n_tiers
        prompts = phase.generate_prompts(want)
        for rec, cap in zip(prompts, captured):
            cfg = cap["cfg"]
            out.append({
                "phase": pid,
                "tier": rec["metadata"]["tier"],
                "kind": cap["kind"],
                "content_key": cap["content_key"],
                "baseline_prompt": cap["baseline_prompt"],
                "meta": rec["metadata"],
                "cfg": cfg,
            })
    # thin to n_per_phase per phase, spread across tiers
    by_phase: dict[int, list[dict]] = {}
    for r in out:
        by_phase.setdefault(r["phase"], []).append(r)
    final = []
    for pid, rows in by_phase.items():
        step = max(1, len(rows) // n_per_phase)
        final.extend(rows[::step][:n_per_phase])
    return final


# ---------------------------------------------------------------------------
# Candidate templates
# ---------------------------------------------------------------------------
import candidates  # noqa: E402  (same directory)


def render(variant: str, row: dict) -> str:
    if variant == "baseline":
        return row["baseline_prompt"]
    fn = getattr(candidates, f"render_{variant}")
    return fn(row)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
OR_PROVIDER_ORDER: list[str] = []   # e.g. ["Baidu"]; set from --or-provider
OR_NO_REASONING = False              # set from --no-reasoning


def generate_one(client, prompt: str, model: str = MODEL, provider: str = "anthropic") -> dict:
    """One story. provider 'anthropic' uses the Messages API (thinking off on
    models that default to adaptive); 'openrouter' uses OpenRouter's
    OpenAI-compatible chat endpoint with OPEN_ROUTER_API_KEY."""
    if provider == "openrouter":
        import httpx2 as httpx
        for attempt in range(5):
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['OPEN_ROUTER_API_KEY']}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": MAX_TOKENS if OR_NO_REASONING else 4 * MAX_TOKENS,
                      "messages": [{"role": "user", "content": prompt}],
                      # some endpoints refuse to disable reasoning; then keep it low and excluded, with room
                      "reasoning": {"enabled": False} if OR_NO_REASONING else {"effort": "low", "exclude": True},
                      **({"provider": {"order": OR_PROVIDER_ORDER, "allow_fallbacks": False}} if OR_PROVIDER_ORDER else {})},
                timeout=300,
            )
            if r.status_code in (429, 500, 502, 503, 529):
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                raise RuntimeError(f"openrouter {r.status_code}: {r.text[:300]}")
            d = r.json()
            choice = d["choices"][0]
            text = choice["message"].get("content") or ""
            usage = d.get("usage", {})
            details = usage.get("completion_tokens_details") or {}
            if "provider" in d:
                usage["_provider"] = d["provider"]
            return {"story": text, "stop_reason": "max_tokens" if choice.get("finish_reason") == "length" else "end_turn",
                    "in_tokens": usage.get("prompt_tokens", 0), "out_tokens": usage.get("completion_tokens", 0),
                    "reasoning_tokens": details.get("reasoning_tokens", 0), "upstream": d.get("provider", "")}
        raise RuntimeError("gave up (openrouter)")

    import anthropic
    kwargs = {}
    if not model.startswith("claude-haiku"):
        kwargs["thinking"] = {"type": "disabled"}  # stories do not need thinking; keeps output tokens comparable
    for attempt in range(5):
        try:
            r = client.messages.create(model=model, max_tokens=MAX_TOKENS, messages=[{"role": "user", "content": prompt}], **kwargs)
            text = "".join(b.text for b in r.content if b.type == "text")
            return {"story": text, "stop_reason": r.stop_reason, "in_tokens": r.usage.input_tokens, "out_tokens": r.usage.output_tokens}
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            time.sleep(2 ** attempt)
    raise RuntimeError("gave up")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="baseline,v1")
    ap.add_argument("--n-per-phase", type=int, default=3)
    ap.add_argument("--phases", default="0,1,2,3,4,5,6")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--model", default=MODEL, help="generator model id (default: the production Haiku)")
    ap.add_argument("--provider", default="anthropic", choices=["anthropic", "openrouter"])
    ap.add_argument("--or-provider", default="", help="OpenRouter upstream provider(s) to pin, comma-separated, e.g. Baidu")
    ap.add_argument("--no-reasoning", action="store_true", help="OpenRouter: ask for reasoning disabled (400 on endpoints that require it)")
    ap.add_argument("--dry-run", action="store_true", help="write prompts only, no API calls")
    args = ap.parse_args()

    load_env()
    global OR_PROVIDER_ORDER, OR_NO_REASONING
    OR_PROVIDER_ORDER = [s.strip() for s in args.or_provider.split(",") if s.strip()]
    OR_NO_REASONING = args.no_reasoning
    out_dir = args.out if args.out.is_absolute() else Path(__file__).resolve().parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    phases = [int(p) for p in args.phases.split(",")]
    rows = build_configs(args.seed, args.n_per_phase, phases)
    print(f"{len(rows)} configs across phases {phases}")

    variants = args.variants.split(",")
    jobs = []
    for v in variants:
        for i, row in enumerate(rows):
            prompt = render(v, row)
            jobs.append((v, i, row, prompt))

    (out_dir / "prompts.jsonl").write_text(
        "\n".join(json.dumps({"variant": v, "idx": i, "phase": row["phase"], "tier": row["tier"], "kind": row["kind"],
                              "content_key": row["content_key"], "prompt": p, "meta": {k: row["meta"][k] for k in ("name", "age", "grade", "verb", "noun", "adjective", "tone", "location", "goal", "features")}},
                             ensure_ascii=False) for v, i, row, p in jobs) + "\n", encoding="utf-8")
    if args.dry_run:
        print("dry run: prompts written to", out_dir / "prompts.jsonl")
        return

    client = None
    if args.provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
    print(f"generator: {args.model} via {args.provider}")
    results: dict[str, list[dict]] = {v: [] for v in variants}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(generate_one, client, p, args.model, args.provider): (v, i, row, p) for v, i, row, p in jobs}
        for n, fut in enumerate(as_completed(futs), 1):
            v, i, row, p = futs[fut]
            res = fut.result()
            results[v].append({"variant": v, "idx": i, "phase": row["phase"], "tier": row["tier"], "kind": row["kind"],
                               "content_key": row["content_key"], "age": row["meta"]["age"], "grade": row["meta"]["grade"],
                               "verb": row["meta"]["verb"], "noun": row["meta"]["noun"], "adjective": row["meta"]["adjective"],
                               "prompt": p, "model": args.model, **res})
            if n % 10 == 0:
                print(f"  {n}/{len(jobs)} done ({time.time() - t0:.0f}s)")
    tot_in = tot_out = 0
    for v in variants:
        rows_v = sorted(results[v], key=lambda r: r["idx"])
        (out_dir / f"{v}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows_v) + "\n", encoding="utf-8")
        v_in = sum(r["in_tokens"] for r in rows_v); v_out = sum(r["out_tokens"] for r in rows_v)
        tot_in += v_in; tot_out += v_out
        trunc = sum(r["stop_reason"] == "max_tokens" for r in rows_v)
        print(f"{v}: {len(rows_v)} stories, truncated={trunc}, mean in={v_in / max(1, len(rows_v)):.0f} mean out tokens={v_out / max(1, len(rows_v)):.0f}")
    print(f"tokens in={tot_in} out={tot_out}; at Haiku standard rates ~${tot_in / 1e6 * 1.0 + tot_out / 1e6 * 5.0:.3f}")


if __name__ == "__main__":
    main()
