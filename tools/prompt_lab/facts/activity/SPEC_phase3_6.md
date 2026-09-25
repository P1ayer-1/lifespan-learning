# Per-activity fact bank, phases 3 and 6

Phase 3 (`phase_3_activities.json`, tiers 7-9, grades 6-8, ages ~11-14) and
phase 6 (`phase_6_activities.json`, tier 13, grade 12, ages ~17-18) each name
one activity per story prompt, the same as phase 0
(`tools/prompt_lab/facts/activity/SPEC.md`). Measured on the committed
pre-pilot prompts (curriculum-learning ce15c91, seed 42): the phase-level
domain bank (`config/facts/phase_3.json`, `phase_6.json`) reaches only 17 of
1,000 phase-3 prompts and 59 of 1,000 phase-6 prompts, because it matches by
a >= 3-term overlap between the activity sentence and the fact text, and most
activities in these phases share no three words with any domain fact. The
rest fall back to a domain-only prompt, the mode measured at ~15-30% false
statements (`docs/DECISIONS.md`, 2026-09-23 night). This bank gives every
phase-3 and phase-6 activity its own verified facts, exactly as phase 0's
did.

Unlike phase 0, an arc's activity is one **band's** goal, not the whole arc:
`arcs.yaml`'s 2026-09-23 schema gives `basic_learning` and `advanced_learning`
a different goal per two-tier band, both sampled under the same
`content_key` at runtime (`engine/tiers.py`: `content_key=content_type.key`;
`engine/arcs.py`: both kinds report `kind="arc"`). A phase-3 arc that spans
tiers 6-7 and 8-9 in both learning modes therefore has up to four distinct
goal texts under one content_key, and phase_3_activities.json /
phase_6_activities.json list one entry per (content_key, kind, band), not
one per content_key. Facts still key on `content_key` alone, because that is
the only field `engine/facts.py` matches on (see "Where facts land" below);
entries sharing a content_key across bands pool their facts together at
merge time. Assign each such entry to a writer as its own activity; do not
collapse bands sharing a content_key into one write-up, or half the phase's
stories for that arc get a fact written for the wrong goal.

## Writing facts (`_gen3/part{K}.json`, `_gen6/part{K}.json`)

Same 12-facts-with-hook rule as phase 0. For each assigned activity (one row
of `_gen3/assign_part{K}.json` / `_gen6/assign_part{K}.json`) write **12
facts**, each with a **hook**.

A fact must be:

- **True without exception, or with the exception stated in the fact
  itself.** Phase 0 required no exceptions at all because a young child
  cannot hold a qualifier; phases 3 and 6 can, so "usually", "in most
  circumstances", "under standard conditions" etc. are fine when the fact
  needs them to stay true — but the exception must be written into the
  15-35 words, not left implicit.
- **Phase 3 (grades 6-8, ages ~11-14): a mechanism, a named historical or
  civic fact, or simple causal science is fine when stated precisely and
  correctly at that level** (e.g. "sound travels faster through water than
  air", "the Roman Empire's western half fell in 476 CE"). Not a
  research-frontier or contested claim, not calculus- or proof-level math,
  not something that needs a diagram to state in words.
- **Phase 6 (grade 12, age ~17-18): quantitative and abstract facts are
  fine** — a named study, a formula, a statistic, a philosopher's argument,
  an economic mechanism — provided it is stated so a general-knowledge
  reader (not a specialist) can follow it without the diagram, proof or
  citation the fact is drawn from. Numbers, dates, names and attributions
  must be exactly correct; a fact that gets a name, date or number wrong is
  not "close enough."
- **One idea**, one or two sentences, at most about 35 words (up from phase
  0's 25 words, since these readers can hold a longer clause), in language a
  textbook or a well-informed adult would use at that grade. A story must be
  able to show all of it; do not bundle two claims into one fact even if
  they are related (a cause and its named discoverer are two facts, not
  one).
- **Directly about the activity's actual band goal** (the `activity` field
  of the assigned row, not the arc's other bands). Spread the 12 across
  different parts of the activity; no two may be paraphrases of each other.
- **Numbers stated as given, and hedged only where the source itself is
  approximate.** An exact figure ("water expands about nine percent when it
  freezes", "the trolley problem was posed by Philippa Foot in 1967") stays
  exact; a figure that is genuinely a range or an estimate says so ("about
  340 meters per second", "roughly a third of"). Do not present an estimate
  as if it were exact, and do not manufacture false precision.
- **Safe and age-appropriate for the band.** Phase 3 (ages 11-14): no fact
  that states or implies an unsafe practice (lab safety, tool use, driving,
  substances) as fine without an adult or a stated safeguard; sensitive
  topics (puberty, mental health, substances) may be named factually but not
  instructively. Phase 6 (ages 17-18): more of the curriculum's own topics
  are already sensitive by design (`learning_health_hygiene`'s tier 12-13
  band covers consent and contraception; `learning_practical_life` covers
  driving and leases) — a fact may state the real mechanism or the real
  number, but never a fact that reads as instructions for evading a safety
  or legal safeguard, and no fact naming a real, identifiable private
  individual.
- **Not culturally narrow presented as universal.** Same rule as phase 0:
  write facts true across the practices a reader might meet, or name the
  specific tradition, source or jurisdiction the fact holds in (a tax or
  legal fact from `taxes`, `mortgages_and_rent`, `how_laws_get_made` etc.
  must name the country or say "in many jurisdictions", since these differ
  by country and the activity does not specify one).
- **Storyable, per the template's fact rule**
  (`engine/story_prompt.py`, added in commit 4d8b1f3): "Every part of the
  fact must come through: a listener who knew nothing else could learn the
  whole fact from the story," and any word the fact names must be said in
  one short line of dialogue. A fact only a diagram, a table or a chain of
  three intermediate steps can convey will fail this the way tier 0's
  now-retired facts did (`facts/activity/revisions.json`); if a fact needs
  more than about two sentences to state, it needs to be split or dropped,
  not compressed.
- **No paraphrase duplicates** within an activity's 12, and no duplicate of
  a fact already in `config/facts/phase_3.json` / `phase_6.json`'s existing
  domain-level facts for the same subject.

The **hook** is one short scene suggestion showing how the fact could come
up in a story a reader this age would actually be in (a real problem,
decision or mistake — not a lecture from an adult). It must not suggest
anything unsafe, illegal for the reader's age, or a shortcut around a stated
safeguard as fine.

### Known false claims (do not write anything like them)

No phase-3 or phase-6 stories have been generated yet (`docs/DECISIONS.md`,
2026-09-25: the per-activity bank is built *before* any story is generated),
so there are no phase-3/6-specific judge notes to draw on. These are the
generator's recorded failure modes from other phases and from the pre-bank
domain-fact review, which the same generator (GLM 5.3) will carry into
phase 3 and 6 to whatever a fact leaves it room for
(`docs/DECISIONS.md`, 2026-09-23 and 2026-09-23 night):

- **Garbling an injected number or direction it was given exactly**: a
  Titanic lifeboat count changed in the retelling; "shorter in the morning"
  reversed to the wrong time of day. A fact with a number, a direction or a
  before/after order is exactly the kind that gets mangled; keep such facts
  short and single-clause so there is less to garble.
- **Inventing its own mechanism, analogy or explanation beyond the fact it
  was given** — the generator's own top source of false statements at
  every phase measured (~15-30%, never the injected fact itself). A fact
  that states the mechanism explicitly, in the words the story should use,
  leaves less gap for the model to fill with an invented one ("hot tap on
  the right" as an invented, wrong default; a base-rate sum that silently
  did not add up; wrong genetics reasoning) — these were what Haiku invented
  when a prompt named only a domain and no fact.
- **Inventing a specific quantity, count or name the fact did not give** —
  e.g. tier-0's regeneration review found invented paint colors and counts
  filling in where the fact was silent. A phase-3/6 fact with a name, date,
  formula or statistic should give the reader nothing to invent around it;
  leave a fact abstract (no specific number) rather than implying one that
  is not stated.

Output, one file per part, UTF-8 JSON, same shape as phase 0:

    {"part": K, "facts": [{"content_key": "...", "fact": "...", "hook": "..."}, ...]}

`content_key` is the assigned row's `content_key` field exactly (from
`_gen3/assign_part{K}.json` / `_gen6/assign_part{K}.json`), not the row's
`id` — `id` (e.g. `learning_math#3`) only disambiguates rows in the
assignment file when several bands share a content_key; it is bookkeeping
and does not appear in the fact bank.

## Verifying facts (`_verify3/part{K}.json`, `_verify6/part{K}.json`)

An independent reviewer checks every fact in one part against the rules
above, most importantly: is it true without exception or with the exception
stated, is it safe and age-appropriate for the band, is it precisely and
correctly stated (names, dates, numbers, attributions), is it storyable in
one or two sentences, is it one idea, and is it actually about the assigned
row's band goal and not a different band of the same arc. Be strict: when in
doubt, it is `false`. Use web search for anything you are not certain of,
especially named studies, historical dates, formulas and attributed
quotations.

    [{"i": 0, "verdict": "true" | "false", "reason": "..."}, ...]

`i` is the fact's index in that part's `facts` list; every index appears
once. Only `true` facts ship.

## Where facts land

`merge_builds.py activity-facts <phase>` (extended for this build; phase 0
still defaults with no argument) reads `_gen{phase}/part*.json` +
`_verify{phase}/part*.json` against `phase_{phase}_activities.json`, and
writes the kept, content_key-tagged facts into `facts/phase_{phase}.json`
**alongside** the domain-level facts already there (the `domain`-keyed facts
in `config/facts/phase_3.json` / `phase_6.json`, copied into
`tools/prompt_lab/facts/phase_3.json` / `phase_6.json` when they were built)
— exactly what phase 0 did: domain facts stay, content_key facts are added.
`engine/facts.py::FactBank` already reads both kinds from the same file (its
`__init__` splits on `f.get("content_key")` vs `f.get("domain")`), so no
generator code changes are needed once the merged file is installed back
into `config/facts/phase_3.json` / `phase_6.json` (the same copy step used
for phase 0, `ad97bc6`).

Commands:

    python tools/prompt_lab/merge_builds.py activity-facts 3
    python tools/prompt_lab/merge_builds.py activity-facts 6

