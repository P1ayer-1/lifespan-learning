# Tier 0 production corpus

Generated 2026-09-24 from 1,000 tier-0 training prompts using seed 42, with the
v5 story template plus the fact rule (every part of the fact must come
through; any word the fact names is said in dialogue) and the revised
per-activity fact bank (12 facts retired, 4 reworded; commit 4d8b1f3). The
fixes were tested first on the 123 failed configurations of the previous
corpus (`tools/prompt_lab/runs/r10_fact_fixes/NOTES.md`). The previous corpus
is archived with its reviews under
`data/_archive/tier0_2026-09-24_activity_facts/`.

The prompt configurations are unchanged: every name, required word, setting,
tone, age and activity matches the archived manifest row for row. Only `fact`
and `fact_hook` differ, in 184 rows, and the template wording changed, so every
prompt hash is new.

## Generation

- Model: `z-ai/glm-5.3@openrouter/Baidu/fp8/reasoning=low`
- Completed: 1,000/1,000 unique prompt hashes
- Input tokens: 757,712
- Output tokens: 250,019
- Approximate cost: $0.86 at the estimator's list rates ($0.56 in, $1.76 out
  per million tokens); expect the bill to be higher
- Empty stories: 0
- Titles or markdown: 0

The `story_defect` check rejected three completions on the first pass; one
resumption regenerated them cleanly.

## Local quality metrics

From `tools/prompt_lab/corpus_metrics.py` (previous corpus in brackets):

- Mean story length: 171 words (169)
- Mean sentence length: 5.5 words (5.5)
- Mean paragraph count: 5.3 (5.3); paragraph targets are estimates, not a quality signal
- Total required vocabulary slots used: 2,461/3,000, 82.0% (81.3%)
- "because" per story: 0.02 (0.02)
- Generation artefacts (`story_defect`): 0 (0)

## Acceptance status

Both gates ran on Opus. This corpus is **not yet accepted for training**:
failing hashes must be regenerated first.

- Fact check: 956/1,000 pass (37 adds_false_claim, 3 contradicts_fact, 4 fact_missing)
- Age fit: 928/1,000 pass (score 1: 1, 2: 71, 3: 787, 4: 141)
- Regeneration queues: 44 fact + 72 age, 13 in both, 103 stories in total
  (`full/stories.jsonl.regen_queue.jsonl`, `full/stories.jsonl.age_regen_queue.jsonl`)

Against the three tier-0 corpora so far, all reviewed on Opus:

| | v5, no activity facts | activity facts | + fact fixes (this) |
|---|---|---|---|
| pass both gates | 890 | 877 | **897** |
| fact-check pass | 929 | 929 | **956** |
| - adds_false_claim | 64 | 43 | 37 |
| - fact_missing | 5 | 25 | 4 |
| age-fit pass | 942 | 930 | 928 |
| age score 4 | 182 | 178 | 141 |

- The fact rule did what it was for: fact_missing fell from 25 to 4, and false
  claims kept falling.
- Age fit did not improve at corpus scale, unlike the r10 check on the 123
  hardest configurations (97 -> 111 of 123). Pass rate is flat and fewer
  stories reach score 4. Reviewers often note one-line definitions spoken by
  an adult ("Now means at this very moment") as a small minus; that is a
  plausible side effect of the rule to say the fact's word, but age fails
  citing definitions or abstraction fell (21 -> 13), so it costs polish, not
  passes.
- Age fails are muddled plots, forced required words and a few uncorrected
  unsafe acts, not vocabulary or sentence length. They cluster in time words
  (12 of the queued stories), body and senses (9) and opposites (8).

## Artifacts

- `train/prompts.jsonl`: frozen prompt manifest.
- `train/prompts.jsonl.sidecar.json`: seed, generator commit, and counts.
- `full/stories.jsonl`: generated stories.
- `full/stories.jsonl.openrouter_cache.jsonl`: resumable provider cache and token usage.
- `_generation_model.json`: pinned model registry.
- `quality/fact_check/`: fact-check review parts, Opus verdicts, `report.txt`.
- `quality/age_check/`: age-fit review parts, Opus scores, `age_check.jsonl`, `report.txt`.
