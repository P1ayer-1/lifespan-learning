# Per-activity fact bank, phase 0 (ages 3-5)

Every phase-0 story prompt names one activity (`phase_0_activities.json`) and
must turn on one real fact. Until now the generator had to invent that fact
for 935 of 1,000 prompts, and its inventions were the main source of false
claims in the tier-0 review. This bank gives every activity its own verified
facts, so the generator never has to invent one.

## Writing facts (`_gen/partK.json`)

For each assigned activity write **12 facts**, each with a **hook**.

A fact must be:

- **Certainly true in ordinary life**, for every child it could describe. If
  there are common exceptions ("most", "usually", "some kinds"), leave it out
  or state it so the exception cannot make it false.
- **Something a 3-5-year-old can see, hear, touch or do** within this
  activity: what a thing does, looks like, is for, or what people do and why
  in plain words. Not a hidden mechanism (no molecules, germs doing things,
  physics, chemistry), not a scientific explanation.
- **One idea**, one or two short sentences, at most about 25 words, in plain
  words a parent would say to a young child. A story must be able to show all
  of it; do not bundle two claims.
- **Directly about the activity**, so a story about that activity can turn on
  it. Spread the 12 across different parts of the activity; no two may be
  paraphrases of each other.
- **Numbers only when exact and certain** ("a week has seven days", "a child
  has two hands"). No durations or quantities that vary ("seeds sprout in a
  week", "twenty seconds of singing").
- **Safe.** Anything hot, sharp, lit, electrical, medical or involving
  strangers, water or animals is stated as the safe practice with a grown-up
  in charge. Never a fact that shows a young child doing something unsafe.
- **Not culturally narrow presented as universal.** For religious or cultural
  events and blessings, write facts that are true across the practices a
  child might meet (families gather, special food, people light candles or
  lamps in many celebrations and grown-ups handle the flames), or name the
  specific tradition in the fact.

The **hook** is one short scene suggestion showing how the fact could come up
in a story (a want, a small problem, or a mistake the child makes and
corrects). It must not suggest anything unsafe as fine.

Known false claims from the 2026-09-24 reviews, so do not write anything like
them: a planted seed sprouting the next day; heavy things falling faster;
breathing out to float; the moon coming out because the sun set; one Happy
Birthday lasting twenty seconds; red and blue making green; a mirror showing
your shadow; ten baby teeth; a potato being a root; blowing on hot tea making
it cold at once; a rainbow as a triangle; bread being good food for ducks;
stomping on the ground knocking snow off a tree.

Output, one file per part, UTF-8 JSON:

    {"part": K, "facts": [{"content_key": "...", "fact": "...", "hook": "..."}, ...]}

## Verifying facts (`_verify/partK.json`)

An independent reviewer checks every fact in one part against the rules
above, most importantly: is it true without exception in ordinary life, is it
safe, can a 3-5-year-old see it within the activity, is it one idea. Be
strict: when in doubt, it is `false`. Use web search for anything you are not
certain of.

    [{"i": 0, "verdict": "true" | "false", "reason": "..."}, ...]

`i` is the fact's index in that part's `facts` list; every index appears once.
Only `true` facts ship.
