import csv
import random

GENDERS = ['girl', 'boy']


# can make this into class
def load_names():
    names = {"boys": [], "girls": []}
    with open(r'process-names\top_names_unique_2021_2024.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row['name'].strip()
            gender = row['gender'].strip().lower()
            if gender == "girl":
                names["girls"].append(name)
            elif gender == "boy":
                names["boys"].append(name)
    return names


NAMES = load_names()

def get_name(gender):
    if gender == "girl":
        return random.choice(NAMES["girls"])
    else:
        return random.choice(NAMES["boys"])
    

