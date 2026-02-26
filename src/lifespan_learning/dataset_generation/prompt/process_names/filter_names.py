from datasets import load_dataset
import json
from lifespan_learning.dataset_generation.prompt import load_list
from collections import defaultdict

# load phases and tiers
phase_configs = load_list(r'config\phases.yaml', key='phases')
tier_configs = load_list(r'config\tiers.yaml')


# Build lookup: tier_id -> age_range
tier_age_lookup = {
    tier["tier"]: tier["age_range"]
    for tier in tier_configs
}

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



# Keep only rank rows
rank_dataset = dataset.filter(lambda x: x["Indicator"] == "Rank")

# Convert VALUE to int safely
rank_dataset = rank_dataset.map(
    lambda x: {"RankValue": int(x["VALUE"])}
)

year_top_names = defaultdict(set)

for row in rank_dataset:
    year = int(row["REF_DATE"])
    rank = row["RankValue"]

    if rank <= 100:
        name = row["First name at birth"].strip().title()
        year_top_names[year].add(name)


phase_name_filters = {}

for phase_id, data in phase_mappings.items():
    start_year, end_year = data["birth_year_range"]

    excluded_names = set()

    for year in range(start_year, end_year + 1):
        if year in year_top_names:
            excluded_names.update(year_top_names[year])

    phase_name_filters[phase_id] = {
        "age_range": data["age_range"],
        "birth_year_range": data["birth_year_range"],
        "excluded_names": sorted(excluded_names)
    }

print(phase_name_filters)

# YEARS = {2021, 2022, 2023, 2024}
# GENDERS = {'Boy', 'Girl'}

# # name -> { gender, rank }
# best_name_entry = {}

# for year in YEARS:
#     for gender in GENDERS:
#         # Filter rows for this year & gender
#         filtered = [
#             row for row in dataset
#             if row['Year'] == year and row['Gender'] == gender
#         ]

#         # Sort by ranking (lower = better)
#         filtered.sort(key=lambda x: x['Ranking by Gender & Year'])

#         # Take top 100 entries
#         for row in filtered[:100]:
#             name = row['First Name'].strip()
#             rank = row['Ranking by Gender & Year']

#             # If name not seen yet, store it
#             if name not in best_name_entry:
#                 best_name_entry[name] = {
#                     'gender': gender,
#                     'rank': rank
#                 }
#             else:
#                 # If seen, keep the better-ranked one
#                 if rank < best_name_entry[name]['rank']:
#                     best_name_entry[name] = {
#                         'gender': gender,
#                         'rank': rank
#                     }

# # Count by gender
# gender_counts = {'Boy': 0, 'Girl': 0}
# for entry in best_name_entry.values():
#     gender_counts[entry['gender']] += 1

# # change json output to dict with gender as key and list of names as value
# final_output = {}
# for name, entry in best_name_entry.items():
#     gender = entry['gender']
#     if gender not in final_output:
#         final_output[gender] = []
#     final_output[gender].append(name)

# # Write json output
# with open(output_path, 'w', newline='', encoding='utf-8') as jsonfile:
#     json.dump(final_output, jsonfile, indent=4)


# print(f"Total unique names: {len(best_name_entry)}")
# print(f"Boys: {gender_counts['Boy']}")
# print(f"Girls: {gender_counts['Girl']}")
# print(f"Output written to: {output_path}")
