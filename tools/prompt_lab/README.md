# prompt_lab

The prompt-template experiment harness used on 2026-09-23 to choose the
template now in `engine/story_prompt.py`. Everything here calls the API and
spends money; nothing in the package imports it.

| Script | What it does | Model |
| --- | --- | --- |
| `gen_ab.py` | Renders the same sampled configs through the repo template (`baseline`) and the candidates in `candidates.py`, generates stories | Haiku 4.5 (the production generator) |
| `judge.py` | Text metrics plus a blind judge: guesses the grade band from the text alone, then rates level fit, educational value, coherence, naturalness, lecture-likeness. `--export` hands the blind stories to a subagent judge (preferred, free); the API judge is the fallback | subagent, or Opus 5 low effort |
| `lexicon_audit.py` | Audits `config/lexicons/*.json`: part of speech, fitness, earliest grade band per word | Haiku 4.5 |
| `lexicon_build.py` | API fallback for the graded lexicons. Preferred path: one subagent per phase writes `lex_build/_gen/phase_{i}.json`, then `merge_builds.py lexicons` sanitizes and deduplicates (a word belongs to its earliest phase) | subagents (fallback Sonnet 5) |
| `mix_blind.py` | Shuffles several runs' stories under opaque ids into blind parts so a judge cannot favour a generator; `unmix` writes each run's `baseline.judged.jsonl` back | subagents |
| `fact_check_export.py` | Fact-consistency gate for a generated corpus: pairs each story with its injected fact, exports review parts, and `apply` turns failing verdicts into `<stories>.regen_queue.jsonl` plus a per-phase report | subagents |
| `age_check_export.py` | Age-fit gate for a generated corpus: exports each story with its target age, grade and reading-level instruction; `apply` collects the subagent scores (`age_check_gate`'s 0-4 scale, pass at 3) into `age_check.jsonl`, `<stories>.age_regen_queue.jsonl` and a report | subagents |
| `factbank.py` | API fallback for the fact bank. Preferred path: one subagent per phase writes `facts/_gen/phase_{i}.json` (15 facts per domain), an independent subagent writes verdicts to `facts/_verify/phase_{i}.json`, then `merge_builds.py facts` keeps only verdict `true` and writes `facts/phase_{i}.json` in the format `engine/facts.py` reads | subagents (fallback Sonnet 5 + Opus 5) |

Rule (owner, 2026-09-23): LLM labor such as judging, fact writing and lexicon
building runs as Claude Code subagents on the Max plan; API credit is spent only
on `gen_ab.py`, which must use the production generator. Generator choice (2026-09-23): `gen_ab.py --model/--provider` compares generators on
identical prompts; OpenRouter models are pinned with `--or-provider` (GLM 5.3 cannot
run with reasoning off on any OpenRouter provider; low effort costs ~80 tokens a
story). Run from this directory with the `lifespan` env, e.g.

    micromamba run -n lifespan python gen_ab.py --variants baseline,v2 --n-per-phase 3 --seed 3 --out runs/r3
    micromamba run -n lifespan python judge.py runs/r3 --variants baseline,v2

`runs/r1`, `runs/r2` hold the measured rounds (stories, prompts and judge
output); `lex_audit/report.txt` is the lexicon audit. `factbank.py` and
`lexicon_build.py` cache every API result under `_cache/`, so a run killed
mid-way (the 2026-09-23 runs died on an exhausted credit balance) resumes
where it stopped.

To install a fact bank: copy `facts/phase_{i}.json` to
`src/lifespan_learning/dataset_generation/prompt/config/facts/`. To install
rebuilt lexicons: copy `lex_build/phase_{i}.json` over `config/lexicons/`.
Both change every prompt hash, so they must land before the exam freeze.
