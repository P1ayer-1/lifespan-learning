# r10: fact fixes (commit 4d8b1f3) on the 123 failed tier-0 configurations (2026-09-24)

Why: the tier-0 corpus with activity facts queued 123 of 1,000 stories (71
fact-check, 70 age-fit, 18 both). Two fixes followed: the story template now
requires every part of the fact to come through and any word the fact names
to be said in dialogue, and `facts/activity/revisions.json` retires 12 facts
and rewords 4 that kept producing tangled stories.

Setup: the 123 failing configurations, two arms, one fresh GLM 5.3 story each
(same model, upstream and settings as production):

- `control/`: the exact committed tier-0 prompts (old template, old facts).
  Measures how many failures pass just by sampling again.
- `fixed/`: the same configurations built with the fixed template and bank.
  40 of the 123 draw a different fact (the rotation shifts in revised
  activities); the other 83 keep their fact and change only in the template.

Both arms were shuffled together (`key.json`, seed 10) and exported to 7
blind parts per gate, reviewed by the Opus `story-fact-checker` and
`story-age-fit-reviewer` subagents. Reviewers saw the fact but not the arm.

| | control | fixed |
|---|---|---|
| pass both gates | 77/123 | **100/123** |
| fact-check pass | 95 | 110 |
| - fact_missing | 13 | **0** |
| - adds_false_claim | 14 | 11 |
| - contradicts_fact | 1 | 2 |
| age-fit pass (score >= 3) | 97 | 111 |
| age score 4 | 10 | 12 |
| required words used | 299/369 | 303/369 |

By subgroup (pass both gates): fact changed, control 20/40 vs fixed 34/40;
fact unchanged, control 57/83 vs fixed 66/83. So both fixes contribute: the
template rule alone removes fact_missing (10 -> 0 where the fact is the same),
and the revised facts carry most of the age-fit gain.

Paired by configuration: fixed passes where control fails 38 times, the
reverse 15 times (62 both pass, 8 both fail). A sign test on the 53
discordant pairs gives p ~ 0.002.

Caveats: these are the corpus's hardest configurations, one story per arm, so
absolute pass rates are low for both and will be higher on the full corpus.
The control shows resampling alone passes 77/123 (63%), which is why a
regeneration pass without the fixes would also look like progress. Remaining
fixed-arm fails are mostly invented details (wrong counts, paint colours,
rules like "dogs get a bath outside") and muddled plots, not the fact.
