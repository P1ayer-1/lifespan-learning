# Tier 0 production corpus (archived: activity facts, before the fact fixes)

Archived 2026-09-24. Superseded by the corpus in `data/tier0/`, built with the
fact rule and revised fact bank from commit 4d8b1f3. Paths below are relative
to this archive directory.

Generated 2026-09-24 from 1,000 tier-0 training prompts using seed 42, with the
v5 story template and, for the first time, a verified fact for every prompt
drawn from the per-activity fact bank (`tools/prompt_lab/facts/activity/`,
commit ad97bc6). It replaces the v5 corpus, which is archived with its full
reviews under `data/_archive/tier0_2026-09-24_template_v5/`; that corpus had
no fact for 935 of its 1,000 prompts.

The prompt configurations are unchanged: every name, required word, setting,
tone, age and activity matches the archived manifest row for row. Only `fact`,
`fact_hook` and (for the 65 prompts that previously drew a domain fact)
`domain` differ, so every prompt hash is new. 533 distinct facts are used, none
more than 6 times.

## Generation

- Model: `z-ai/glm-5.3@openrouter/Baidu/fp8/reasoning=low`
- Completed: 1,000/1,000 unique prompt hashes
- Input tokens: 685,636
- Output tokens: 241,766
- Approximate cost: $0.81 at the estimator's list rates ($0.56 in, $1.76 out
  per million tokens); expect the bill to be higher, as with earlier corpora
- Empty stories: 0
- Titles or markdown: 0

The first pass wrote 994 stories. The `story_defect` check rejected six
completions as retryable (four with sentences run together, one ending
mid-sentence, one with a leaked markup tag); one resumption regenerated all six
cleanly.

## Local quality metrics

From `tools/prompt_lab/corpus_metrics.py` (v5 corpus without activity facts in
brackets):

- Mean story length: 169 words (168)
- Mean sentence length: 5.5 words (5.6)
- Mean paragraph count: 5.3 (5.3); paragraph targets are estimates, not a quality signal
- Required verb used: 703/1,000 (733)
- Required noun used: 841/1,000 (853)
- Required adjective used: 896/1,000 (904)
- Total required vocabulary slots used: 2,440/3,000, 81.3% (83.0%)
- "because" per story: 0.02 (0.04)
- Generation artefacts (`story_defect`): 0 (0)

## Acceptance status

Generation is complete and both gates have run on Opus, but this corpus is
**not yet accepted for training**: failing hashes must be regenerated first.

- Fact check: 929/1,000 pass (43 adds_false_claim, 3 contradicts_fact, 25 fact_missing)
- Age fit: 930/1,000 pass (score 1: 1, 2: 69, 3: 752, 4: 178)
- Regeneration queues: 71 fact + 70 age, 18 in both, 123 stories in total
  (`full/stories.jsonl.regen_queue.jsonl`, `full/stories.jsonl.age_regen_queue.jsonl`)

Against the v5 corpus, reviewed the same way on Opus (929 fact, 942 age):

- Invented false claims fell from 64 to 43. The facts replaced most of what the
  generator used to make up.
- fact_missing rose from 5 to 25, because every story now has a fact it can
  fail to convey. Most of these are stories that show the idea but never use
  the word the fact defines ("primary colours", "icons", "author", "countdown").
- The fact-check pass count is therefore unchanged at 929.
- Age-fit fails rose from 58 to 70. Almost all are confusing or
  self-contradicting plots, not vocabulary, sentence length or safety.
  Uncorrected unsafe scenes are rare: 3 of the 70 reasons mention safety.
- Fails cluster in abstract concept activities: number words (12 of the
  queued stories), time words (11), writing (9), then categories, senses,
  opposites and reading (6 each). Facts such as "a week has seven days" or
  "tomorrow becomes today" draw the generator into tangled counting and
  time reasoning that a 3-5-year-old cannot follow.

## Artifacts

- `train/prompts.jsonl`: frozen prompt manifest.
- `train/prompts.jsonl.sidecar.json`: seed, generator commit, and counts.
- `full/stories.jsonl`: generated stories.
- `full/stories.jsonl.openrouter_cache.jsonl`: resumable provider cache and token usage.
- `_generation_model.json`: pinned model registry.
- `quality/fact_check/`: fact-check review parts, Opus verdicts, `report.txt`.
- `quality/age_check/`: age-fit review parts, Opus scores, `age_check.jsonl`, `report.txt`.
