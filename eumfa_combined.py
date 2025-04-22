# 1. run bottom up model, extract material demand and eol flows
# 2. map dimensions
# 3. read top down demand, optionally map, calculate residual demand (top down - bottom up) and project residual demand
# 4. run stock model with residual demand to calculate residual eol flows
# 5. calculate total material demand and total eol flow
# 6. run with these inputs flow model
# 7. combine historic and future tables

import logging
from run_eumfa import run_eumfa
import pandas as pd
import csv


"""Choose material and bottom up models"""
bottom_up_sectors_to_consider = ["buildings"]
materials_to_consider = ["concrete"]
downstream_only = False # uses given demand and eol flows and calculates recycling rate, production...
baseyear = 2023


mapping_file_path_buildings_concrete = "data/baseline_combined/mapping_buildings_concrete.csv"

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

#todo extract these functions which are not core to another file

# Function to sanitize file names
def sanitize_filename(filename):
    return filename.replace("=>", "_to_").replace(" ", "_")


def map_dimensions(original_df, mapping_dict):
    # Step 1: Convert mapping_dict to a DataFrame
    mapping_df = pd.DataFrame(mapping_dict)

    # Convert 'factor' to numeric and fill NaN with 1.0
    mapping_df['factor'] = pd.to_numeric(mapping_df['factor'], errors='coerce').fillna(1.0)

    # Make a copy of the original_df and reset index to columns
    df_flat = original_df.reset_index()

    # Initialize a column to hold cumulative factors
    df_flat['cumulative_factor'] = 1.0

    # For each unique original_dimension in mapping_df
    for dimension in mapping_df['original_dimension'].unique():

        # Get the mappings for this dimension
        dimension_mappings = mapping_df[mapping_df['original_dimension'] == dimension]

        # Create mapping dictionaries
        element_to_target_element = dict(
            zip(dimension_mappings['original_element'], dimension_mappings['target_element']))
        element_to_factor = dict(zip(dimension_mappings['original_element'], dimension_mappings['factor']))
        target_dimension = dimension_mappings['target_dimension'].iloc[0]

        # If dimension is in df_flat columns
        if dimension in df_flat.columns:
            # Map the elements
            df_flat[dimension + '_original'] = df_flat[dimension]
            df_flat[dimension] = df_flat[dimension].map(element_to_target_element).fillna(df_flat[dimension])

            # Apply the factors
            df_flat['factor_' + dimension] = df_flat[dimension + '_original'].map(element_to_factor).fillna(1.0)
            df_flat['cumulative_factor'] *= df_flat['factor_' + dimension]

            # Rename the dimension if target_dimension is different
            if target_dimension != dimension:
                df_flat.rename(columns={dimension: target_dimension}, inplace=True)
        else:
            print(f"Dimension '{dimension}' not found in DataFrame columns.")
            continue

    # Apply the cumulative factor to the 'Value' column
    df_flat['value'] *= df_flat['cumulative_factor']

    # Drop the helper columns used for mapping
    helper_columns = [col for col in df_flat.columns if
                      col.startswith('factor_') or col.endswith('_original') or col == 'cumulative_factor']
    df_flat.drop(columns=helper_columns, inplace=True)

    # Group by the new dimensions and sum the values to handle duplicates
    index_columns = [col for col in df_flat.columns if col != 'value']
    remapped_data = df_flat.groupby(index_columns)['value'].sum().reset_index()

    # Set the index back to the dimensions
    remapped_data.set_index(index_columns, inplace=True)

    return remapped_data

# 1. Run bottom-up model
if "buildings" in bottom_up_sectors_to_consider and not downstream_only:
    flows_buildings = run_eumfa("config/buildings.yml")

    if "concrete" in materials_to_consider:
        concrete_flows = {}

        # Filter relevant flows for concrete products
        relevant_flows = [
            "sysenv => Concrete stock in buildings",
            "Concrete stock in buildings => sysenv"
        ]
        mapping_file_path = mapping_file_path_buildings_concrete

        #todo make this an independent function to use for all materials
        for flow_name, flow in flows_buildings.items():
            if flow_name in relevant_flows:
                # Read mapping file
                with open(mapping_file_path, mode='r', newline='', encoding='utf-8') as file:
                    mapping_dict = list(csv.DictReader(file, delimiter=';'))

                print("Mapping dictionary loaded")

                # Map dimensions and save the remapped flow
                concrete_flows[flow_name] = map_dimensions(flow, mapping_dict)
                print(f"Remapped flow: {flow_name}")

        # Save remapped flows to CSV files
        for flow_name, remapped_data in concrete_flows.items():
            output_path = f"data/baseline/output/{sanitize_filename(flow_name)}_concrete_flows.csv"
            remapped_data.to_csv(output_path)
            print(f"Saved remapped flow to: {output_path}")


    if "Plastics" in materials_to_consider:
        relevant_flows = [
            "sysenv => Insulation stock in buildings",
            "Insulation stock in buildings => sysenv"
        ]
        pass

    if "Steel" in materials_to_consider:
        relevant_flows = [
            "sysenv => Steel stock in buildings",
            "Steel stock in buildings => sysenv"
        ]
        pass



if "vehicles" in bottom_up_sectors_to_consider:
    run_eumfa("config/vehicles.yml")
    pass

# 2. For materials (plastics, concrete, steel)
#   a) Top-down material demand - translate dimensions - not necessary for cement
#       I. Read Excel Domestic Demand
#       II. Check for dimensions, translate dimensions
#   b) Calculate residual material demand
#       I. Residual material demand = top-down material demand - bottom-up material demand
#   c) Project residual material demand
#       I. Residual material demand projection = Residual material demand * growth rate (year)
#   d) Run MFA stock with projected residual material demand to get residual EOL flow

if "concrete" in materials_to_consider and downstream_only == False:

    def project_demand(
        top_down_start_value_filepath,
        top_down_growth_rate_filepath,
        bottom_up_demand_filepath,
        result_filepath,
        material_column,
        default_sector,
        base_year=baseyear,
        value_column='value',
        sector_column='End use sector',
        region_column='Region simple',
        default_region='EU28',
        default_material=None,
    ):
        # Read the start value CSV (top-down data)
        start_value_df = pd.read_csv(top_down_start_value_filepath)

        growth_rate_df = pd.read_csv(top_down_growth_rate_filepath)

        bottom_up_demand_df = pd.read_csv(bottom_up_demand_filepath)

        # Standardize the value column name to lowercase
        for df in [start_value_df, growth_rate_df, bottom_up_demand_df]:
            if 'Value' in df.columns:
                df.rename(columns={'Value': 'value'}, inplace=True)

        # Ensure the sector column exists in bottom-up data
        if sector_column not in bottom_up_demand_df.columns:
            bottom_up_demand_df[sector_column] = default_sector

        # Ensure the material column exists in bottom-up data
        if material_column not in bottom_up_demand_df.columns:
            if default_material is None:
                raise ValueError(f"The '{material_column}' column is missing in bottom-up data and no default is set.")
            bottom_up_demand_df[material_column] = default_material

        # Ensure the region column exists in bottom-up data
        if region_column not in bottom_up_demand_df.columns:
            bottom_up_demand_df[region_column] = default_region

        # Ensure the region column exists in start value data
        if region_column not in start_value_df.columns:
            start_value_df[region_column] = default_region

        # Ensure the region column exists in growth rate data
        if region_column not in growth_rate_df.columns:
            growth_rate_df[region_column] = default_region

        # Filter bottom-up demand to include only data for the base year
        demand_base_year_df = bottom_up_demand_df[bottom_up_demand_df['Time'] == base_year]

        # Merge start value with growth rate data on sector, region, and time columns
        merged_df = pd.merge(
            start_value_df,
            growth_rate_df,
            on=[sector_column, region_column, 'Time'],
            how='left',
            suffixes=('_start', '_growth')
        )

        # Merge the result with the bottom-up demand data on material, sector, and region columns
        merged_df = pd.merge(
            merged_df,
            demand_base_year_df[[material_column, sector_column, region_column, value_column]],
            on=[material_column, sector_column, region_column],
            how='left',
            suffixes=('', '_bottom_up')
        )

        # Fill NaN values in the bottom-up demand 'value' column with 0
        merged_df[value_column] = merged_df[value_column].fillna(0)

        # Compute the new 'value' as (start value - bottom-up demand base year value) * growth rate
        merged_df['Projected value'] = (merged_df[f'{value_column}_start'] - merged_df[value_column]) * merged_df[
            f'{value_column}_growth']

        # Select the required columns
        result_df = merged_df[[material_column, sector_column, region_column, 'Time', 'Projected value']]

        # Rename 'Projected value' column back to 'value' if desired
        result_df = result_df.rename(columns={'Projected value': value_column})

        # Save the result to CSV
        result_df.to_csv(result_filepath, index=False)

        print(f"Projected demand has been calculated and saved to {result_filepath}")

    top_down_start_value_filepath = f'data/baseline_cement_stock_flows/input/datasets/start_value.csv'
    top_down_growth_rate_filepath = f'data/baseline_cement_stock_flows/input/datasets/growth_rate.csv'
    bottom_up_demand_filepath = f'data/baseline/output/sysenv__to__Concrete_stock_in_buildings_concrete_flows.csv'
    result_filepath = f'data/baseline_cement_stock_flows/input/datasets/demand_future.csv'

    project_demand(
        top_down_start_value_filepath,
        top_down_growth_rate_filepath,
        bottom_up_demand_filepath,
        result_filepath,
        material_column='Concrete product simple',
        default_sector='Buildings',
        default_region='EU28',
        default_material=None,
    )

    #call residual demand stock model
    residual_flows_concrete_future = run_eumfa("config/cement_stock.yml")


#   f) Calculate total material demand and eol flow
    #todo: generalize
    def calculate_total_flows(
        bottom_up_filepath,
        top_down_filepath,
        output_filepath,
        default_region='EU28',
        bottom_up_end_use_sector='Buildings'
    ):


        # Read the bottom-up data
        bottom_up_df = pd.read_csv(bottom_up_filepath)

        # Read the top-down data
        top_down_df = pd.read_csv(top_down_filepath)

        # Ensure 'End use sector' exists in both DataFrames
        if 'End use sector' not in bottom_up_df.columns:
            bottom_up_df['End use sector'] = bottom_up_end_use_sector  # Default 'Buildings'

        if 'End use sector' not in top_down_df.columns:
            # If missing, add a default or handle appropriately
            top_down_df['End use sector'] = 'Unspecified'  # Adjust as necessary

        # Ensure 'Region simple' exists in both DataFrames
        if 'Region simple' not in bottom_up_df.columns:
            bottom_up_df['Region simple'] = default_region

        if 'Region simple' not in top_down_df.columns:
            top_down_df['Region simple'] = default_region

        # Ensure both DataFrames have the same columns in the same order
        required_columns = ['Time', 'Region simple', 'Concrete product simple', 'End use sector', 'value']
        bottom_up_df = bottom_up_df[required_columns]
        top_down_df = top_down_df[required_columns]

        # Combine the two DataFrames
        combined_df = pd.concat([bottom_up_df, top_down_df], ignore_index=True)

        # Group by relevant columns and sum the 'value'
        total_flows_df = combined_df.groupby(
            ['Time', 'Region simple', 'Concrete product simple', 'End use sector'], as_index=False)['value'].sum()

        # Save the result to a CSV file
        total_flows_df.to_csv(output_filepath, index=False)

        print(f"Total flows have been calculated and saved to {output_filepath}")




    # File paths for future demand
    bottom_up_demand_filepath = 'data/baseline/output/sysenv__to__Concrete_stock_in_buildings_concrete_flows.csv'
    top_down_demand_filepath = 'data/baseline_cement_stock_flows/output/export/flows/concrete_market_future__end_use_stock_future.csv'
    output_demand_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_demand.csv'

    # Calculate concrete demand flows
    calculate_total_flows(
        bottom_up_filepath=bottom_up_demand_filepath,
        top_down_filepath=top_down_demand_filepath,
        output_filepath=output_demand_filepath,
        default_region='EU28',
        bottom_up_end_use_sector='Buildings'
    )

    # File paths for EOL flows
    bottom_up_eol_filepath = 'data/baseline/output/Concrete_stock_in_buildings__to__sysenv_concrete_flows.csv'
    top_down_eol_filepath = 'data/baseline_cement_stock_flows/output/export/flows/end_use_stock_future__cdw_collection_future.csv'
    output_eol_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_eol_flows.csv'

    #Calculate concrete eol flows
    calculate_total_flows(
        bottom_up_filepath=bottom_up_eol_filepath,
        top_down_filepath=top_down_eol_filepath,
        output_filepath=output_eol_filepath,
        default_region='EU28',
        bottom_up_end_use_sector='Buildings'
)

if "plastics" in materials_to_consider and downstream_only == False:
    pass
if "steel" in materials_to_consider and downstream_only == False:
    pass

#   g) Downstream modell rechnen
if "concrete" in materials_to_consider:

    flows_concrete = run_eumfa("config/cement_flows.yml")
    #todo combine historic and future tables



if "plastics" in materials_to_consider:
    pass
if "steel" in materials_to_consider:
    pass
