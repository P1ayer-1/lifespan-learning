import json
from pathlib import Path

SRC = Path(r"C:\Users\noahp\AppData\Local\Temp\claude\D--Lifespan\dfdd6285-9b19-43ca-a1e9-0a17de9e9aab\scratchpad\smoke_source_prompts.jsonl")
OUT = Path(r"C:\Users\noahp\AppData\Local\Temp\claude\D--Lifespan\dfdd6285-9b19-43ca-a1e9-0a17de9e9aab\scratchpad\smoke_prompts_20.jsonl")

COUNT_PER_PHASE = {0: 3, 1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2}

by_phase = {i: [] for i in range(7)}
with SRC.open("r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        by_phase[row["metadata"]["phase"]].append(row)

selected = []
for phase in range(7):
    n = COUNT_PER_PHASE[phase]
    chosen = by_phase[phase][:n]
    assert len(chosen) == n, f"phase {phase} only has {len(chosen)} prompts, need {n}"
    selected.extend(chosen)

assert len(selected) == 20

with OUT.open("w", encoding="utf-8", newline="\n") as f:
    for row in selected:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print(f"Wrote {len(selected)} prompts to {OUT}")
for row in selected:
    m = row["metadata"]
    print(f"  phase={m['phase']} tier={m['tier']} age={m['age']} grade={m['grade']!r} hash={row['prompt_hash'][:12]}")
