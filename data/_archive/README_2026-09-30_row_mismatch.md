# Phase 3/6 pre-pilot stories retired 2026-09-30 (row mismatch)

`phase3_prepilot_2026-09-30_row_mismatch/stories.jsonl` and
`phase6_prepilot_2026-09-30_row_mismatch/stories.jsonl` hold the train
stories whose prompts changed when activity facts were matched to the
prompt's goal (row) instead of only its content_key. Before the fix a
phase-3 prompt could get a fact written for a sibling row (fractions story,
triangle fact): 380/1000 phase-3 and 280/1000 phase-6 prompts. The 200-story
review (`data/phase{3,6}_prepilot/quality/`, commit 07c981c) measured
phase-3 either-fail 34.9% on mismatched prompts vs 17.5% on matched ones.
Kept for the record; not training data.
