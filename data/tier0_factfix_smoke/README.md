# Tier 0 fact-alignment smoke comparison

Generated 2026-09-23 from the same 20 tier-0 activity, character, setting,
vocabulary, and style configurations as `../tier0_smoke` (seed 42). Only the
knowledge instruction changed: a verified fact is injected only with a strong
activity match; otherwise the activity itself is the knowledge domain. One of
the 20 corrected prompts retained an injected fact.

Generator identity was hidden from the Opus blind judge. Both generators used
reasoning effort `low`. Generation completed 20/20 for each model.

| Metric | Original full | Corrected full | Original Flash | Corrected Flash |
| --- | ---: | ---: | ---: | ---: |
| Input tokens | 11,741 | 10,677 | 11,741 | 10,677 |
| Output tokens | 5,379 | 4,807 | 4,348 | 3,836 |
| Mean words | 166 | 153 | 143 | 136 |
| Exact JK-SK band guess | 8/20 | **15/20** | 6/20 | **17/20** |
| Within one band | 20/20 | 20/20 | 20/20 | 20/20 |
| Reading-level fit (1-5) | 3.70 | **4.30** | 3.45 | **4.25** |
| Educational value (1-5) | **3.45** | 3.20 | **3.25** | 2.90 |
| Coherence (1-5) | 3.60 | **4.25** | 3.90 | **3.95** |
| Naturalness (1-5) | 3.30 | **3.70** | 3.25 | **3.45** |
| Lecture-like | 7/20 | **0/20** | 7/20 | **2/20** |
| Required vocabulary used | 56/60 | 56/60 | 47/60 | **52/60** |
| Titles/markup | 0/20 | 0/20 | 0/20 | 0/20 |
| Truncated | 0/20 | 0/20 | 0/20 | 0/20 |

Approximate generation-token cost at the same observed provider rates was
$0.035 for corrected full GLM 5.3 and $0.002 for corrected Flash. Judging cost
is excluded.

## Findings

Removing weakly related injected facts fixed the dominant failure mode. Full
GLM's lecture rate fell from 35% to 0%, its exact age-band signal nearly
doubled, and coherence and naturalness both improved substantially. Educational
value fell slightly because activity-only prompts no longer force a separate
fact into every story; that is the intended tradeoff, since post-generation
fact checking can validate relevant details without creating two stitched
lessons.

The blind judge found one explicitly false independent claim in corrected full
story 16 (pinching the nose was said to quiet a cracker's crunch). It also
flagged a dubious wet-wheel claim in story 7. Corrected Flash retained two
lecture-like stories and several thin, garbled, or questionable explanations,
including a shaky butter mechanism and a vague needle-size claim. These results
confirm that factual review must cover every generated claim, not only an
injected fact. `tools/prompt_lab/fact_check_export.py` now exports activity and
knowledge context for activity-only prompts and reserves `fact_missing` for
prompts that actually contain a required fact.

## Decision

Proceed with full GLM 5.3 as the Tier 0 production generator. Keep the current
Baidu `fp8`, low-reasoning route, then run the factual-accuracy and age-fit gates
and regenerate failures before accepting the tier. Do not scale Flash yet: its
roughly 18x lower generation cost does not compensate for its lower educational
value, coherence, naturalness, and vocabulary compliance in this small sample.

This is a 20-story smoke test, not a final estimate of the acceptance rate.
Measure the first production batch's fact-check and age-gate pass rates before
starting later tiers.

## Artifacts

- `train/prompts.jsonl`: corrected shared prompt set.
- `full/`: GLM 5.3 stories and resumable provider cache.
- `flash/`: GLM 5.3 Flash stories and resumable provider cache.
- `../../tools/prompt_lab/runs/tier0_factfix_full/`: normalized full-model run and blind judgments.
- `../../tools/prompt_lab/runs/tier0_factfix_flash/`: normalized Flash run and blind judgments.
