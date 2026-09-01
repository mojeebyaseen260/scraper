"""
Fetch the top USA cities per state (by population) from the GeoNames free
dataset and save to locations.py. No API key needed - uses public download.

Set TOP_N to control how many cities per state (default 20, ranked by
population descending).
"""

import io
import os
import csv
import json
import zipfile
import requests

GEONAMES_URL = "https://download.geonames.org/export/dump/US.zip"

# How many top cities (by population) to keep per state.
TOP_N = 40

# GeoNames feature codes for populated places
PLACE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLX", "PPLS"}

# GeoNames admin1 code -> state name
ADMIN1_CODES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington DC", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "US Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands"
}

def fetch_geonames():
    print("Downloading GeoNames US data (~30MB)...")
    r = requests.get(GEONAMES_URL, stream=True, timeout=120)
    r.raise_for_status()
    
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    chunks = []
    for chunk in r.iter_content(chunk_size=65536):
        chunks.append(chunk)
        downloaded += len(chunk)
        if total:
            pct = downloaded * 100 // total
            print(f"\r  Downloading... {pct}%", end="", flush=True)
    print("\n  Download complete!")
    
    data = b"".join(chunks)
    
    print("  Parsing data...")
    # state -> {city_name: max_population}  (dedupe duplicate names, keep biggest)
    states = {}

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("US.txt") as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            for row in reader:
                if len(row) < 15:
                    continue
                # Columns: geonameid, name, asciiname, alternatenames, lat, lng,
                #          feature_class, feature_code, country, cc2,
                #          admin1_code, admin2_code, admin3, admin4, population, ...
                feature_class = row[6]
                feature_code  = row[7]
                admin1        = row[10]
                name          = row[2].strip()  # asciiname
                try:
                    population = int(row[14]) if row[14] else 0
                except ValueError:
                    population = 0

                if feature_class != "P":
                    continue
                if feature_code not in PLACE_CODES:
                    continue
                if not name or not admin1:
                    continue

                state_name = ADMIN1_CODES.get(admin1)
                if not state_name:
                    continue

                cities = states.setdefault(state_name, {})
                if name not in cities or population > cities[name]:
                    cities[name] = population

    # Keep the TOP_N most-populated cities per state, ordered biggest first.
    result = {}
    for state in sorted(states):
        ranked = sorted(states[state].items(), key=lambda kv: (-kv[1], kv[0]))
        result[state] = [name for name, _pop in ranked[:TOP_N]]
    return result


def build_locations_py(states_data, out_path="locations.py"):
    print(f"  Writing {out_path}...")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f'"""\nUSA - Top {TOP_N} cities per state by population '
                f'(auto-generated from GeoNames)\n"""\n\n')
        f.write('LOCATIONS = {\n    "USA": {\n')
        
        for state, cities in states_data.items():
            safe_state = state.replace('"', '\\"')
            f.write(f'        "{safe_state}": [\n')
            for i in range(0, len(cities), 6):
                chunk = cities[i:i+6]
                row = ", ".join(f'"{c.replace(chr(34), chr(92)+chr(34))}"' for c in chunk)
                f.write(f'            {row},\n')
            f.write('        ],\n')
        
        f.write('    }\n}\n')
    
    total_cities = sum(len(v) for v in states_data.values())
    print(f"\n  Done! {len(states_data)} states, {total_cities:,} cities -> {out_path}")
    return total_cities


if __name__ == "__main__":
    print("=" * 50)
    print("USA Cities Fetcher (GeoNames)")
    print("=" * 50)
    
    out = os.path.join(os.path.dirname(__file__), "locations.py")
    
    data = fetch_geonames()
    total = build_locations_py(data, out_path=out)
    
    print(f"\nTotal cities added: {total:,}")
    print("locations.py is ready!")
