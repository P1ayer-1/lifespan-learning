# Tier 0 generator smoke comparison

Generated 2026-09-23 from the same 20 tier-0 prompts (seed 42). Generator
identity was not shown to the judge. Both variants used reasoning effort low.

| Metric | GLM 5.3 (Baidu, fp8) | GLM 5.3 Flash (DeepInfra) |
| --- | ---: | ---: |
| Completed stories | 20/20 | 20/20 |
| Input tokens | 11,741 | 11,741 |
| Output tokens | 5,379 | 4,348 |
| Mean words | 166 | 143 |
| Exact JK-SK band guess | 8/20 | 6/20 |
| Within one band | 20/20 | 20/20 |
| Reading-level fit (1-5) | 3.70 | 3.45 |
| Educational value (1-5) | 3.45 | 3.25 |
| Coherence (1-5) | 3.60 | 3.90 |
| Naturalness (1-5) | 3.30 | 3.25 |
| Lecture-like | 7/20 | 7/20 |
| Required vocabulary used | 56/60 | 47/60 |
| Titles/markup | 0/20 | 0/20 |
| Truncated | 0/20 | 0/20 |

At the provider prices observed for this comparison, the generation tokens cost
approximately $0.040 for GLM 5.3 and $0.002 for Flash. This excludes judging.

## Decision

Do not scale either generator yet. Full GLM 5.3 is the stronger candidate on
the curriculum-facing measures, but both variants expose the same upstream
prompt problem: the sampled curriculum activity and the injected fact can be
only loosely related. The resulting story often contains two lessons stitched
together, with the fact delivered as a lecture. Seven stories from each model
were judged lecture-like. The judge also found a counting contradiction in both
versions of prompt 13, and two possible fact/implication errors in the full-model
set.

Before another paid batch, make fact selection activity-specific (or omit the
fact when no close match exists), regenerate these same 20 prompt identities,
and repeat this comparison. Keep full GLM 5.3 as the quality baseline; reconsider
Flash after the prompt confound is removed.

## Artifacts

- `train/prompts.jsonl`: the shared prompt set.
- `full/`: GLM 5.3 stories, model registry, and resumable provider cache.
- `flash/`: GLM 5.3 Flash stories, model registry, and resumable provider cache.
- `../../tools/prompt_lab/runs/tier0_full/`: normalized inputs and blind judgments.
- `../../tools/prompt_lab/runs/tier0_flash/`: normalized inputs and blind judgments.
