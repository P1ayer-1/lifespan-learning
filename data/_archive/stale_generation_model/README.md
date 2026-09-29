`_generation_model.json` here (model `claude-haiku-4-5`) was created at
`data/_generation_model.json` on 2026-09-23 by `generate_responses.py`'s old
`default_registry_path` auto-creation (commit 7784e52, "Data side: exam
split, batch response generator, age-check gate, seeded names, smoke
batch"), the run that wrote `data/smoke/smoke_stories_20.jsonl` with
`--provider anthropic` before the 2026-09-23 switch to GLM 5.3. It predates
that switch and nothing current reads it: no README or script under
`data/` references `data/_generation_model.json` by that root-level path
(only tier-local `_generation_model.json` files, e.g.
`data/tier0/_generation_model.json`, the canonical registry for the current
tier-0/pre-pilot corpus). Archived rather than deleted (2026-09-25 leakage
audit fix, finding 2) so the provenance of the early smoke run stays on
record. Auto-creation of registries is removed as of the same fix;
generation now requires an explicit `--corpus-registry` or
`--new-corpus-registry`.
