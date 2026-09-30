import argparse
import csv
import json
from lifespan_learning.dataset_generation.prompt.config_loader import load_list
from collections import defaultdict


def build_phase_mappings(phase_configs, tier_configs, current_year):
    """Build phase -> age_range & birth_year_range mapping."""
    tier_age_lookup = {
        tier["tier"]: tier["age_range"]
        for tier in tier_configs
    }

    phase_mappings = {}

    for phase in phase_configs:
        phase_id = phase["id"]
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

    return phase_mappings


def load_and_prepare_rank_dataset(csv_path):
    """Load the Statistics Canada CSV and return its Rank rows, normalized.

    Plain csv instead of the Hugging Face `datasets` loader this used to call:
    same rows and fields, no heavy dependency for a 645k-line file.
    """
    rank_dataset = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["Indicator"] != "Rank" or not row["VALUE"]:
                continue
            rank_dataset.append({
                "Year": int(row["REF_DATE"]),
                "RankValue": int(float(row["VALUE"])),
                "Name": row["First name at birth"].strip().title(),
                "Sex": row["Sex at birth"].strip().title(),
            })
    print(f"Rank rows in dataset: {len(rank_dataset)}")
    return rank_dataset


def build_top_names_ranked(rank_dataset, max_rank=100):
    """Build year -> {name: best_rank} mapping."""
    year_top_names = defaultdict(dict)

    for row in rank_dataset:
        year = row["Year"]
        rank = row["RankValue"]
        name = row["Name"]

        if rank <= max_rank:
            if name not in year_top_names[year]:
                year_top_names[year][name] = rank
            else:
                year_top_names[year][name] = min(
                    year_top_names[year][name],
                    rank
                )

    return year_top_names


def build_top_names_gendered(rank_dataset, max_rank=100):
    """Build year -> gender -> {name: best_rank} mapping."""
    year_top_names = defaultdict(lambda: defaultdict(dict))

    for row in rank_dataset:
        year = row["Year"]
        rank = row["RankValue"]
        name = row["Name"]
        gender = row["Sex"]

        if rank <= max_rank:
            if name not in year_top_names[year][gender]:
                year_top_names[year][gender][name] = rank
            else:
                year_top_names[year][gender][name] = min(
                    year_top_names[year][gender][name],
                    rank
                )

    return year_top_names


def build_phase_name_filters(phase_mappings, year_top_names):
    """Build phase -> excluded names based on birth year ranges."""
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

    return phase_name_filters

def build_phase_name_filters_gendered(phase_mappings, year_top_names):
    """Build phase -> gender -> [list of names] based on birth year ranges."""
    phase_name_filters = {}

    for phase_id, data in phase_mappings.items():
        start_year, end_year = data["birth_year_range"]

        # gender -> {name: best_rank}
        gender_name_ranks = defaultdict(dict)

        for year in range(start_year, end_year + 1):
            if year in year_top_names:
                for gender, names_dict in year_top_names[year].items():
                    for name, rank in names_dict.items():
                        if name not in gender_name_ranks[gender]:
                            gender_name_ranks[gender][name] = rank
                        else:
                            gender_name_ranks[gender][name] = min(
                                gender_name_ranks[gender][name],
                                rank
                            )

        # Convert to gender -> sorted list of names
        phase_name_filters[phase_id] = {
            gender: [
                name for name, _ in sorted(
                    name_rank_dict.items(),
                    key=lambda x: x[1]
                )
            ]
            for gender, name_rank_dict in gender_name_ranks.items()
        }

    return phase_name_filters


def print_phase_summary(phase_name_filters):
    """Print count of excluded names per phase."""
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

if __name__ == "__main__":
    # Run from the prompt/ directory (config paths are relative to it):
    #   python data_handling/process_names/filter_names.py
    #       -> config/names/names_gendered.json, rank <= 100 (main characters)
    #   python data_handling/process_names/filter_names.py --max-rank 1000 --out config/names/names_gendered_rank1000.json
    #       -> the larger pool the side characters draw from (~1,170-1,280 names per gender per phase)
    # A name is kept for a phase if it ranked <= max-rank for its sex in any
    # birth year that phase's ages imply (current year minus the tier age range).
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-rank", type=int, default=100)
    parser.add_argument("--out", default="config/names/names_gendered.json")
    parser.add_argument("--current-year", type=int, default=2026)
    parser.add_argument("--csv", default="data_handling/process_names/input/canada_name_popularity.csv")
    cli = parser.parse_args()

    gendered = True

    # Load configs
    phase_configs = load_list("config/phases.yaml", key="phases")
    tier_configs = load_list("config/tiers.yaml", key="tiers")

    current_year = cli.current_year

    # Build phase mappings
    phase_mappings = build_phase_mappings(
        phase_configs,
        tier_configs,
        current_year
    )

    # Load and process dataset
    rank_dataset = load_and_prepare_rank_dataset(cli.csv)

    if gendered:
        year_top_names_gendered = build_top_names_gendered(rank_dataset, max_rank=cli.max_rank)
        phase_name_filters = build_phase_name_filters_gendered(
            phase_mappings,
            year_top_names_gendered
        )

        with open(cli.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(phase_name_filters, f, indent=2, ensure_ascii=False)
        print({p: {g: len(v) for g, v in d.items()} for p, d in phase_name_filters.items()})

    else:
        # Build yearly top names
        year_top_names = build_top_names_ranked(rank_dataset)

        # Build phase name filters
        phase_name_filters = build_phase_name_filters(
            phase_mappings,
            year_top_names
        )

        # Print summary
        print_phase_summary(phase_name_filters) # func wont work with gendered version, need to rewrite to print summary

        # Calculate overlap
        calculate_overlap(list(phase_name_filters.keys())) # func wont work with gendered version, need to rewrite to calculate overlap by gender