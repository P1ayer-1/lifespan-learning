# r9: v5 template vs production template, phase 0 (2026-09-24)

Why: the tier-0 corpus review (1,000 stories) failed 27 on fact-check and 51 on
age-fit. The failures traced to the phase-0 thinking move ("says it in simple
words" produced "X because Y" lines, where most false claims sat), to
self-invented facts (935/1,000 tier-0 prompts carry no verified fact), and to
unsafe scenes (candles, stoves, climbing) under a prompt with no safety rule.

Setup: `gen_ab.py --variants baseline,v5 --phases 0 --n-per-phase 100 --seed 7`
on the production generator (z-ai/glm-5.3, OpenRouter, Baidu, reasoning low).
`baseline` is `engine/story_prompt.py` as installed; `v5` is `candidates.render_v5`.
Both variants were shuffled under opaque ids (`key.json`) into 5 blind parts per
gate and reviewed by the `story-fact-checker` and `story-age-fit-reviewer`
subagents (`make_review.py export|score`).

| | baseline | v5 |
|---|---|---|
| any fail (fact or age < 3) | 8 | 5 |
| fact-check fails | 4 | 1 |
| age-fit fails | 5 | 4 |
| age score 4 (of 100) | 26 | 44 |
| unsafe-scene fails | 4 | 1 |
| required words used | 267/300 | 240/300 |
| "because" per story | 0.26 | 0.00 |
| mean words | 168 | 167 |

v5's fails: one invented detail (star-shaped grape seed), one child alone in a
store, one forced-word tangle, one tangled cause chain, and one story cut off
mid-word ("Tedd", finish_reason stop), a generator artefact the new
`story_defect` check in `openrouter_provider.py` now rejects as retryable.

A first v5 cut also said "every line of dialogue counts as a paragraph"; it
pushed 74/100 stories over 2x max_paragraphs at the same word count
(`v5_dialogue_note.jsonl`) and was dropped. Paragraph targets are estimates
with no empirical basis (owner, 2026-09-24), so paragraph counts are not a
quality signal here.

Caveats: n=100 per arm, one seed; the fail-count difference (8 vs 5) is
directional, not significant on its own. The age-4 share (26 vs 44) and the
safety fails are the clearer signals. v5 trades ~9 points of required-word
coverage for fewer forced sentences.

Not yet done: installing v5 into `engine/story_prompt.py` changes every prompt
hash, so it needs a decision about the frozen tier-0 manifest.
