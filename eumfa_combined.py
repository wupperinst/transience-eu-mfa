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
import glob
import os
import csv
from src.common.combine_flows import FlowCalculator



"""Choose material and bottom up models"""
bottom_up_sectors_to_consider = ["buildings"]
materials_to_consider = ["concrete"]
downstream_only = False # uses given demand and eol flows and calculates recycling rate, production...
baseyear = 2023


mapping_file_path_buildings_concrete = "data/baseline_combined/mapping_buildings_concrete.csv"

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")



flow_calculator = FlowCalculator()
# 1. Run bottom-up model

import pandas as pd
import gc
import sys

if __name__ == "__main__":
    try:
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
                        concrete_flows[flow_name] = flow_calculator.map_dimensions(flow , mapping_dict)
                        print(f"Remapped flow: {flow_name}")

                # Save remapped flows to CSV files
                for flow_name, remapped_data in concrete_flows.items():
                    output_path = f"data/baseline/output/{FlowCalculator.sanitize_filename(flow_name)}_concrete_flows.csv"
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

            top_down_start_value_filepath = f'data/baseline_cement_stock_flows/input/datasets/start_value.csv'
            top_down_growth_rate_filepath = f'data/baseline_cement_stock_flows/input/datasets/growth_rate.csv'
            bottom_up_demand_filepath = f'data/baseline/output/sysenv__to__Concrete_stock_in_buildings_concrete_flows.csv'
            result_filepath = f'data/baseline_cement_stock_flows/input/datasets/demand_future.csv'

            flow_calculator.project_demand(
                top_down_start_value_filepath,
                top_down_growth_rate_filepath,
                bottom_up_demand_filepath,
                result_filepath,
                material_column='Concrete product simple',
                default_sector='Buildings',
                default_region='EU28',
                default_material=None,
                base_year=baseyear
            )

            #call residual demand stock model
            residual_flows_concrete_future = run_eumfa("config/cement_stock.yml")


        #   f) Calculate total material demand and eol flow

            # File paths for future demand
            bottom_up_demand_filepath = 'data/baseline/output/sysenv__to__Concrete_stock_in_buildings_concrete_flows.csv'
            top_down_demand_filepath = 'data/baseline_cement_stock_flows/output/export/flows/concrete_market_future__end_use_stock_future.csv'
            output_demand_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_demand.csv'

            # Calculate concrete demand flows
            flow_calculator.calculate_total_flows(
                bottom_up_filepath=bottom_up_demand_filepath,
                top_down_filepath=top_down_demand_filepath,
                output_filepath=output_demand_filepath,
                default_region='EU28',
                bottom_up_end_use_sector='Buildings'
            )

        # TODO:
        # 1. Differentiate building outflows by age cohort:
        #    a) Historic age cohort
        #    b) Future age cohort
        # 2. Adjust historic age cohort outflows:
        #    a) Subtract baseline scenario historic outflows.
        #    b) Add scenario-specific historic outflows back.
        # 3. Add future age cohort outflows to future EOL flows.

            # File paths for EOL flows
          #  bottom_up_eol_filepath = 'data/baseline/output/Concrete_stock_in_buildings__to__sysenv_concrete_flows.csv'
            top_down_eol_filepath = 'data/baseline_cement_stock_flows/output/export/flows/end_use_stock_future__cdw_collection_future.csv'
            output_eol_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_eol_flows.csv'
            # store residual eol flow as input for future eol flow
            eol_data = pd.read_csv(top_down_eol_filepath)
            eol_data.to_csv(output_eol_filepath, index=False)

        if "plastics" in materials_to_consider and downstream_only == False:
            pass
        if "steel" in materials_to_consider and downstream_only == False:
            pass

        #   g) Downstream modell rechnen
        if "concrete" in materials_to_consider:

            flows_concrete = run_eumfa("config/cement_flows.yml")


        # Combine historic and future tables


            results_folder = "data/baseline_cement_stock_flows/output/export/flows"

            # Get all historic and future file pairs
            historic_files = glob.glob(os.path.join(results_folder, "*historic*.csv"))
            for historic_file in historic_files:
                future_file = historic_file.replace("historic", "future")
                if os.path.exists(future_file):
                    try:
                        # Read both files
                        historic_df = pd.read_csv(historic_file)
                        future_df = pd.read_csv(future_file)

                        # Combine the dataframes
                        combined_df = pd.concat([historic_df, future_df])

                        # Group by all columns except 'value' and sum the 'value' column
                        combined_df = combined_df.groupby(
                            [col for col in combined_df.columns if col != 'value'], as_index=False
                        )['value'].sum()

                        # Save the combined table
                        output_file = historic_file.replace("historic", "combined")
                        combined_df.to_csv(output_file, index=False)
                        print(f"Combined table saved to: {output_file}")
                    except Exception as e:
                        print(f"Error merging files: {historic_file} and {future_file}. Error: {e}")
                else:
                    print(f"Future file not found for: {historic_file}")

        if "plastics" in materials_to_consider:
            pass
        if "steel" in materials_to_consider:
            pass

            # Clean up DataFrames
            del historic_df, future_df, combined_df
            gc.collect()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        sys.exit(0)
