from datasets import load_dataset
import json
from config_loader import load_list

# load phases and tiers
phase_configs = load_list(r'config\phases.yaml', key='phases')
tier_configs = load_list(r'config\tiers.yaml')


csv_path = r'process-names\input\17100147.csv'
output_path = r'config\names\top_names_unique_2021_2024.json'

dataset = load_dataset('csv', data_files=csv_path, split='train')

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
