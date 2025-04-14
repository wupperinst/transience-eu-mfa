# run buildings (reduced), extract material demand and eol, map dimensions, run vehicles (reduced), extract material demand and eol, map dimensions,
# read bottom up concrete, map bottom up concrete,
# calculate residual demand concrete with results from bottom up, project residual demand concrete, calculate residual stocks concrete, residual eol concrete,
#calculate total material demand concrete, calculate total eol concrete,
# run with these inputs downstream concrete,
# repeat for steel, plastics

import pandas as pd
import logging
from run_eumfa import run_eumfa
import os

# 0. Choose material and bottom up models
bottom_up_sectors_to_consider = ["buildings"]
materials_to_consider = ["concrete"]
downstream_only = False # uses given demand and eol flows

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

# 1. Run bottom-up model
if "builings" in bottom_up_sectors_to_consider and downstream_only == False:

    flows = run_eumfa("config/buildings.yml")

    # 2. Sort results by material and continue with respective material
    for flow_name, flow in flows.items():
        df = pd.DataFrame.from_dict(flow)
        if "Glass product" in df.index.names:
            print("glass")
        elif "Steel product" in df.index.names:
            print("steel")
        elif "Concrete product" in df.index.names:
            print("concrete")
        elif "Insulation product" in df.index.names:
            print("insulation")
        else:
            print("no material found")


    #todo do this for all materials
    #todo add "if material in materials_to_consider"

    # 3. Translate dimensions
    concrete_flows = {}
    # Define mappings for dimensions
    # todo: do this with an excel
    concrete_product_mapping = {
        "Precast concrete (not reinforced)": "Precast",
        "Reinforced concrete": "Reinforced",
        "Other concrete": "Other",
    }

    region_mapping = {
        "AUT": "Austria",
        "BEL": "Belgium",
        "SWE": "Sweden",
    }
    for flow_name, flow in flows.items():
        df = pd.DataFrame.from_dict(flow)

        # Check for required dimensions
        if "Concrete product" in df.index.names:
            # Map "Concrete product" dimension
            df.index = df.index.set_levels(
                df.index.levels[df.index.names.index("Concrete product")].map(
                    lambda x: map_with_logging(x, concrete_product_mapping, "Concrete product")
                ),
                level="Concrete product"
            )

            # Map "Region" dimension only for "Concrete product"
            if "Region" in df.index.names:
                df.index = df.index.set_levels(
                    df.index.levels[df.index.names.index("Region")].map(
                        lambda x: map_with_logging(x, region_mapping, "Region")
                    ),
                    level="Region"
                )

        # Add the updated DataFrame to the new dictionary
        concrete_flows[flow_name] = df

        # Ergebnisse (demand, eol) speichern - als csv und später aus csv auslesen, oder als df?
        for flow_name, df in concrete_flows.items():
            sanitized_name = sanitize_filename(flow_name)
            output_path = f"data/baseline/output/{sanitized_name}_concrete_flows.csv"
            df.to_csv(output_path)



if "vehicles" in bottom_up_sectors:
    # run_eumfa("config/vehicles.yml")
    pass

if "concrete" in materials_to_consider and downstream_only == False:
# 2. for material (plastics, concrete, steel)
#   a) Top down material demand - dimensionen übersetzen
#       I. Read Excel Domestic Demand
#       II. Check for dimensions, translate dimenstions

#   b) Rest material demand berechnen
#       I. rest material demand = top down material demand - bottom up material demand

#   c) Rest material demand projezieren - und speichern?
#       I. Read growth rate
#       II. Define function
#       eg. Rest material demand projection = rest material demand * growth rate (year)

#   d) Rest material demand modell aufrufen
#       I. Check if all data is available and log
#       II. Run MFA(Material)
#       III. Return flows

#   e) Ergebnisse (demand, eol) speichern - als csv und später aus csv auslesen, oder als df?
#       I. Save flows

if "concrete" in materials_to_consider:
#   f) Total material demand and eol berechnen
#       I. Read all flows
#       II. Add bottom up and top down demand and eol
#       III. Save results

#   g) Downstream modell rechnen
#       I. Check if all data is available and log
#       II. Run downstream MFA(Material)
#       III. Save results


# Helper function to log missing keys during mapping
def map_with_logging(value, mapping, dimension_name):
    if value not in mapping:
        logging.warning(f"Unmapped value '{value}' in dimension '{dimension_name}'")
    return mapping.get(value, value)

# Function to sanitize file names
def sanitize_filename(filename):
    return filename.replace("=>", "_to_").replace(" ", "_")