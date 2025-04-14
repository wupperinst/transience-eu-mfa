#thoughts: vielleicht erstmal die bottom up modelle jeweils laufen lassen, ergebnisse übersetzen und zwischenspeichern, top down berechnen für alle jahre, dann jeweils für jedes material extra modell laufen lassen das kombiniert ist


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

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

# Helper function to log missing keys during mapping
def map_with_logging(value, mapping, dimension_name):
    if value not in mapping:
        logging.warning(f"Unmapped value '{value}' in dimension '{dimension_name}'")
    return mapping.get(value, value)


# 1. Run bottom-up model
flows = run_eumfa("config/buildings.yml")

# 2. Sort results by material
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

# 3. Translate dimensions
concrete_flows = {}
# Define mappings for dimensions
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


# 4. Ergebnisse (demand, eol) speichern - als csv und später aus csv auslesen, oder als df?
# Function to sanitize file names
def sanitize_filename(filename):
    return filename.replace("=>", "_to_").replace(" ", "_")

for flow_name, df in concrete_flows.items():
    sanitized_name = sanitize_filename(flow_name)
    output_path = f"data/baseline/output/{sanitized_name}_concrete_flows.csv"
    df.to_csv(output_path)




# 5. Top down material demand - dimensionen übersetzen

# 6. Rest material demand berechnen

# 7. Rest material demand projezieren - und speichern?

# 8. Rest material demand modell aufrufen

# 9. Ergebnisse (demand, eol) speichern - als csv und später aus csv auslesen, oder als df?



# 10. Total material demand berechnen

# 11. Total EoL berechnen
    #speichern als df oder excel?

# 12. Downstream modell rechnen