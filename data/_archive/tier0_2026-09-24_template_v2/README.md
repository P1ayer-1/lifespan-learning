# Tier 0 production corpus

Generated 2026-09-24 from 1,000 tier-0 training prompts using seed 42.

## Generation

- Model: `z-ai/glm-5.3@openrouter/Baidu/fp8/reasoning=low`
- Completed: 1,000/1,000 unique prompt hashes
- Input tokens: 529,635
- Output tokens: 271,512
- Approximate generation cost: $1.95 at the observed provider rates
- Empty stories: 0
- Truncated stories: 0
- Titles or markdown: 0

The first provider pass wrote 832 stories and queued 168 retryable failures.
Two resumptions recovered 140 and 28 stories respectively. No hard failures
were recorded.

## Local quality metrics

- Mean story length: 167 words
- Mean sentence length: 6 words
- Mean paragraph count: 5
- Required verb used: 838/1,000
- Required noun used: 930/1,000
- Required adjective used: 946/1,000
- Total required vocabulary slots used: 2,714/3,000 (90.5%)

## Acceptance status

Generation is complete, but this corpus is **not yet accepted for training**.
The 1,000 stories have been exported into 25 forty-story review chunks under
`quality/fact_check/`. Every factual claim must be checked, including stories
whose prompt had no injected fact. Failing hashes must be regenerated before
acceptance. The age-fit gate should also run before the tier is finalized.

## Artifacts

- `train/prompts.jsonl`: frozen prompt manifest.
- `train/prompts.jsonl.sidecar.json`: seed, generator commit, and counts.
- `full/stories.jsonl`: generated stories.
- `full/stories.jsonl.openrouter_cache.jsonl`: resumable provider cache and token usage.
- `full/_generation_model.json`: pinned model registry.
- `quality/fact_check/part*.jsonl`: factual-accuracy review inputs (reviewed by the `story-fact-checker` subagent into `part*.verdicts.jsonl`).
- `quality/age_check/part*.jsonl`: age-fit review inputs from `tools/prompt_lab/age_check_export.py` (scored by the `story-age-fit-reviewer` subagent into `part*.age.jsonl`).
