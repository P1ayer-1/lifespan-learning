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

**Accepted: 995 stories, every one passing both gates.** Five prompt
configurations failed three rounds and were dropped from `full/stories.jsonl`
(listed with their last reasons in `full/dropped.jsonl`; the manifest keeps
all 1,000 prompts, so a generator resume would try them again). The queue
files are empty.

Regeneration round 2 (`regen2/`, 2026-09-25): the 19 twice-failed prompts got
one more story each. Fact check 17/19, age fit 15/19, 14 both; the 14 replace
their originals. The five dropped: a counting story that miscounts its toy
monkeys, a snow-day frog, a school nap that turns into night, a picnic at a
grandparent's grave, and a forced-word tangle. Four of the five failed for the
same reason in all three rounds.

First pass, both gates on Opus:

- Fact check: 956/1,000 pass (37 adds_false_claim, 3 contradicts_fact, 4 fact_missing)
- Age fit: 928/1,000 pass (score 1: 1, 2: 71, 3: 787, 4: 141)
- 103 stories failed at least one gate (44 fact, 72 age, 13 both)

Regeneration round 1 (`regen1/`, 2026-09-25): the 103 prompts, unchanged,
got one fresh story each ($0.09 at list rates; a separate output path, because
the provider cache would otherwise return the old story for the same hash).
Both gates ran again on Opus:

- Fact check: 91/103 pass (11 adds_false_claim, 1 contradicts_fact)
- Age fit: 94/103 pass (score 1: 1, 2: 8, 3: 86, 4: 8)
- 84/103 now pass both; 19 fail again (12 fact, 9 age, 2 both). 9 of the 12
  fact fails and all 9 age fails failed the same gate the first time, so these
  configurations are hard for the generator, not unlucky.

All 103 new stories replaced their originals in `full/stories.jsonl`, and the
queue files there now list only the 19 still failing (verdicts and reasons in
`regen1/quality/`). For those 103 hashes, `regen1/quality/` supersedes the
first-pass reviews in `quality/`.

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
- `full/dropped.jsonl`: the five prompts dropped after three failed rounds.
- `regen1/`, `regen2/`: regeneration rounds: the 103 prompts, their new stories and
  provider caches, and both gates' reviews in `regenN/quality/`.
