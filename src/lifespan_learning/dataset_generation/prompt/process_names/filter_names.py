from datasets import load_dataset
import json
from lifespan_learning.dataset_generation.prompt import load_list
from collections import defaultdict


### !!! Need to add gender !!!

# load phases and tiers
phase_configs = load_list(r'config\phases.yaml', key='phases')
tier_configs = load_list(r'config\tiers.yaml')

# Build lookup: tier_id -> age_range
tier_age_lookup = {
    tier["tier"]: tier["age_range"]
    for tier in tier_configs
}


current_year = 2026

phase_mappings = {}

for phase in phase_configs:
    phase_id = phase["id"]  # or phase["name"]
    tier_ids = phase.get("tiers", [])

    ages = []
    for tier_id in tier_ids:
        age_range = tier_age_lookup.get(tier_id)
        if age_range:
            ages.extend(age_range)

    if ages:
        min_age = min(ages)
        max_age = max(ages)

        birth_year_range = [
            current_year - max_age,  # oldest
            current_year - min_age   # youngest
        ]

        phase_mappings[phase_id] = {
            "age_range": [min_age, max_age],
            "birth_year_range": birth_year_range
        }

print(phase_mappings)



csv_path = r'process_names\input\17100147.csv'
output_path = r'config\names\top_names_unique_2021_2024.json'

print(csv_path)


dataset = load_dataset('csv', data_files=csv_path, split='train')

print(f"Total rows in dataset: {len(dataset)}")

# print dataset column names
print(f"Dataset columns: {dataset.column_names}")



# Keep only Rank rows
rank_dataset = dataset.filter(lambda x: x["Indicator"] == "Rank")

# Normalize types
rank_dataset = rank_dataset.map(
    lambda x: {
        "Year": int(x["REF_DATE"]),
        "RankValue": int(x["VALUE"]),
        "Name": x["First name at birth"].strip().title()
    }
)

year_top_names = defaultdict(dict)

for row in rank_dataset:
    year = row["Year"]
    rank = row["RankValue"]
    name = row["Name"]

    if rank <= 100:
        if name not in year_top_names[year]:
            year_top_names[year][name] = rank
        else:
            year_top_names[year][name] = min(
                year_top_names[year][name],
                rank
            )


phase_name_filters = {}

for phase_id, data in phase_mappings.items():
    start_year, end_year = data["birth_year_range"]

    excluded_names = {}

    for year in range(start_year, end_year + 1):
        if year in year_top_names:
            for name, rank in year_top_names[year].items():
                if name not in excluded_names:
                    excluded_names[name] = rank
                else:
                    excluded_names[name] = min(
                        excluded_names[name],
                        rank
                    )

    phase_name_filters[phase_id] = {
        "age_range": data["age_range"],
        "birth_year_range": data["birth_year_range"],
        "excluded_names": dict(
            sorted(excluded_names.items(), key=lambda x: x[1])
        )
    }

print(phase_name_filters)

# print length of excluded names for each phase
for phase_id, data in phase_name_filters.items():
    print(f"Phase {phase_id} - Excluded names: {len(data['excluded_names'])}")


def calculate_overlap(phase_ids: list[str]) -> None:

    for i in range(len(phase_ids)):
        for j in range(i + 1, len(phase_ids)):
            phase_a = phase_ids[i]
            phase_b = phase_ids[j]

            names_a = set(phase_name_filters[phase_a]["excluded_names"].keys())
            names_b = set(phase_name_filters[phase_b]["excluded_names"].keys())

            overlap = names_a.intersection(names_b)

            overlap_a_to_b = (len(overlap) / len(names_a) * 100) if names_a else 0.0
            overlap_b_to_a = (len(overlap) / len(names_b) * 100) if names_b else 0.0

            print(
                f"{phase_a} → {phase_b}: "
                f"{overlap_a_to_b:.2f}% of {phase_a} names appear in {phase_b} "
                f"({len(overlap)} names)"
            )

            print(
                f"{phase_b} → {phase_a}: "
                f"{overlap_b_to_a:.2f}% of {phase_b} names appear in {phase_a}"
            )

            print("-" * 50)

phase_ids = list(phase_name_filters.keys())

calculate_overlap(phase_ids)