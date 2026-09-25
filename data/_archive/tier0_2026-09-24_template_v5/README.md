# Tier 0 production corpus (archived: v5 template, no activity facts)

Archived 2026-09-24. Superseded by the corpus in `data/tier0/`, which uses the
same prompt configurations plus a verified per-activity fact for every prompt.
Paths below are relative to this archive directory.

Generated 2026-09-24 from 1,000 tier-0 training prompts using seed 42, with the
"v5" story template (`engine/story_prompt.py`, phases 0-1 changes; evidence in
`tools/prompt_lab/runs/r9_v5/NOTES.md`). It replaces the first tier-0 corpus,
archived with its full fact-check and age-fit reviews under
`data/_archive/tier0_2026-09-24_template_v2/` (27/1000 fact-check fails, 51/1000
age-fit fails, mostly self-invented mechanisms and unsafe scenes).

The prompt configurations are unchanged: every name, required word, setting,
tone and injected fact matches the archived manifest row for row; only the
prompt wording differs, so every prompt hash is new.

## Generation

- Model: `z-ai/glm-5.3@openrouter/Baidu/fp8/reasoning=low`
- Completed: 1,000/1,000 unique prompt hashes
- Input tokens: 626,967
- Output tokens: 247,976
- Approximate cost: $0.79 at the estimator's list rates ($0.56 in, $1.76 out
  per million tokens); the first corpus billed $1.95 at observed rates for a
  similar token count, so expect more than list
- Empty stories: 0
- Titles or markdown: 0

The first pass wrote 997 stories. The new `story_defect` check in the
OpenRouter provider rejected three completions as retryable, one of each kind
(a story ending mid-sentence, a leaked markup tag, a story written twice); one
resumption regenerated all three cleanly.

## Local quality metrics

From `tools/prompt_lab/corpus_metrics.py` (first corpus in brackets):

- Mean story length: 168 words (167)
- Mean sentence length: 5.6 words (5.6)
- Mean paragraph count: 5.3 (5.0); paragraph targets are estimates, not a quality signal
- Required verb used: 733/1,000 (828)
- Required noun used: 853/1,000 (929)
- Required adjective used: 904/1,000 (946)
- Total required vocabulary slots used: 2,490/3,000, 83.0% (90.1%); the v5
  vocabulary rule prefers skipping a word to forcing it
- "because" per story: 0.04 (0.28)
- Generation artefacts (`story_defect`): 0 (3)

## Acceptance status

Generation is complete and both gates have run, but this corpus is **not yet
accepted for training**: failing hashes must be regenerated first.

Both gates ran on Opus (the reviewer agents default to Fable; owner asked for
Opus on 2026-09-24):

- Fact check: 929/1,000 pass (64 adds_false_claim, 2 contradicts_fact, 5 fact_missing)
- Age fit: 942/1,000 pass (score 1: 5, 2: 53, 3: 760, 4: 182)
- Regeneration queues: 71 fact + 58 age, 19 in both, 110 stories in total
  (`full/stories.jsonl.regen_queue.jsonl`, `full/stories.jsonl.age_regen_queue.jsonl`);
  both stories glued to a second draft (505ded6a, eaa050d8) are in them

Opus is a much stricter fact checker than Fable, so these counts are not
comparable with the first corpus's Fable-reviewed 27 and 51. A like-for-like
check exists for facts only: Fable reviewed 880 of these stories before the
switch (`quality/_fable/`), and on the same 880 prompt configurations the
first corpus had 22 Fable fact fails against 27 here. v5 did **not** reduce
false claims at corpus scale; the r9 A/B's 4 -> 1 was a 100-story sample.
Opus agreed with 23 of those 27 and failed 60 of the 880. No like-for-like
age-fit comparison exists yet.

## Artifacts

- `train/prompts.jsonl`: frozen prompt manifest.
- `train/prompts.jsonl.sidecar.json`: seed, generator commit, and counts.
- `full/stories.jsonl`: generated stories.
- `full/stories.jsonl.openrouter_cache.jsonl`: resumable provider cache and token usage.
- `_generation_model.json`: pinned model registry (the generator's default location; the first corpus kept it in `full/`).
- `quality/fact_check/part*.jsonl`: factual-accuracy review inputs.
- `quality/age_check/part*.jsonl`: age-fit review inputs.
