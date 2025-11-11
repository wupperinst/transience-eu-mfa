# 1. run bottom up model, extract material demand and eol flows
# 2. map dimensions
# 3. read top down demand, optionally map, calculate residual demand (top down - bottom up) and project residual demand
# 4. run stock model with residual demand to calculate residual eol flows
# 5. calculate total material demand and total eol flow
# 6. run with these inputs flow model
# 7. combine historic and future tables

import logging
from run_eumfa import run_eumfa
import glob
import os
import csv
import pandas as pd
import gc
import sys
from src.common.combine_flows import FlowCalculator


"""Choose material and bottom up models"""
bottom_up_sectors_to_consider = ["buildings"]
materials_to_consider = ["concrete"]
downstream_only = False # uses given demand and eol flows and calculates recycling rate, production...
baseyear = 2023


mapping_file_path_buildings_concrete = "data/baseline_combined/mapping_buildings_concrete.csv"
mapping_file_path_buildings_steel = "data/baseline_combined/mapping_buildings_steel.csv"
mapping_file_path_buildings_plastics = "data/baseline_combined/mapping_buildings_plastics.csv"
mapping_file_path_vehicles_steel = "data/baseline_combined/mapping_vehicles_steel.csv"
mapping_file_path_vehicles_plastics = "data/baseline_combined/mapping_vehicles_plastics.csv"

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")



flow_calculator = FlowCalculator()
# 1. Run bottom-up model

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
                        # DataFrame aus xarray/DataArray erzeugen
                        if hasattr(flow, 'to_dataframe'):
                            flow_df = flow.to_dataframe().reset_index()
                        else:
                            flow_df = flow.copy()
                        # Mapping-Datei im original_dimension-Schema einlesen
                        with open(mapping_file_path, mode='r', newline='', encoding='utf-8') as f:
                            mapping_dict = list(csv.DictReader(f, delimiter=';'))
                        # map_dimensions anwenden (nutzt Faktoren & Dimensionstransformation)
                        #todo: checken mappen von einer dimension auf mehrere - insulation proudct, sector b&c, material PUR,EPS
                        mapped_df = flow_calculator.map_dimensions(flow_df, mapping_dict)
                        concrete_flows[flow_name] = mapped_df
                        print(f"Remapped flow (map_dimensions): {flow_name}")

                # Save remapped flows to CSV files
                for flow_name, remapped_data in concrete_flows.items():
                    output_path = f"data/baseline/output/{FlowCalculator.sanitize_filename(flow_name)}_concrete_flows.csv"
                    remapped_data.to_csv(output_path, index=False)
                    print(f"Saved remapped flow to: {output_path}")

            if "plastics" in materials_to_consider and not downstream_only:
                relevant_flows = [
                    "sysenv => Insulation stock in buildings",
                    "Insulation stock in buildings => sysenv"
                ]
                mapping_file_path = mapping_file_path_buildings_plastics

                plastics_flows = {}
                for flow_name, flow in flows_buildings.items():
                    if flow_name in relevant_flows:
                        flow_df = flow.to_dataframe().reset_index() if hasattr(flow, 'to_dataframe') else flow.copy()
                        mapping_df = pd.read_csv(mapping_file_path, sep=None, engine='python')

                        remapped = flow_calculator.map_dimensions_dual_targets(
                            original_df=flow_df,
                            mapping_df=mapping_df,
                            value_col='value',
                            drop_source_dims=True
                        )
                        plastics_flows[flow_name] = remapped
                        print(f"Remapped (dual targets) flow: {flow_name}")

                for flow_name, remapped_data in plastics_flows.items():
                    output_path = f"data/baseline/output/{FlowCalculator.sanitize_filename(flow_name)}_plastics_flows.csv"
                    remapped_data.to_csv(output_path, index=False)
                    print(f"Saved remapped plastics flow to: {output_path}")


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

            # Neue Residual-Berechnung ohne Aggregation
            start_df = pd.read_csv(top_down_start_value_filepath)
            growth_df = pd.read_csv(top_down_growth_rate_filepath)
            bu_df = pd.read_csv(bottom_up_demand_filepath)
            residual_future_df = flow_calculator.compute_residual_flodym(
                start_value_df=start_df,
                bottom_up_df=bu_df,
                growth_rate_df=growth_df,
                base_year=baseyear,
                time_col='Time',
                value_col='value',
                key_cols=None,  # auto-align on intersection after fills
                fill_values_per_df={
                    'bottom_up': {'End use sector': 'Buildings'}
                    # optional: if start/growth need constants, add them here
                    # 'start_value': {'Region simple': 'EU28'},
                    # 'growth_rate': {'Region simple': 'EU28'}
                }
            )
            residual_future_df.to_csv(result_filepath, index=False)
            print(f"Residual future demand saved: {result_filepath}")

            #call residual demand stock model
            residual_flows_concrete_future = run_eumfa("config/cement_stock.yml") # todo check if this calls the right mfa


        #   f) Calculate total material demand and eol flow

            # File paths for future demand
            bottom_up_demand_filepath = 'data/baseline/output/sysenv__to__Concrete_stock_in_buildings_concrete_flows.csv'
            residual_future_demand_filepath = result_filepath  # demand_future.csv (Residual)
            output_demand_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_demand.csv'

            # Total Future Demand (Bottom-up + Residual)
            bu_future_df = pd.read_csv(bottom_up_demand_filepath)
            residual_future_df_reload = pd.read_csv(residual_future_demand_filepath)
            total_future_demand_df = flow_calculator.compute_total_future_flodym(
                key_cols=('Concrete product simple', 'End use sector', 'Region simple'),
                time_col='Time',
                value_col='value',
                base_year=baseyear,  # ensure only future years are summed
                include_base_year=False,
                flows={
                    'bottom_up': bu_future_df,
                    'residual': residual_future_df_reload
                },
                fill_values_per_df={
                    'bottom_up': {'End use sector': 'Buildings', 'Region simple': 'EU28'},
                    'residual': {'End use sector': 'Residual', 'Region simple': 'EU28'}
                }
            )
            total_future_demand_df.to_csv(output_demand_filepath, index=False)
            print(f"Total future demand gespeichert: {output_demand_filepath}")

            # Total Future EOL (Bottom-up EOL + Residual EOL)
            #todo: sort by cohort

            bottom_up_eol_filepath = 'data/baseline/output/Concrete_stock_in_buildings__to__sysenv_concrete_flows.csv'
            residual_eol_filepath = 'data/baseline_cement_stock_flows/output/export/flows/end_use_stock_future__cdw_collection_future.csv'
            output_total_eol_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_eol_flows.csv'

            bu_eol_df = pd.read_csv(bottom_up_eol_filepath)
            residual_eol_df = pd.read_csv(residual_eol_filepath)
            total_future_eol_df = flow_calculator.compute_total_future_flodym(
                key_cols=('Concrete product simple', 'End use sector', 'Region simple'),
                time_col='Time',
                value_col='value',
                base_year=baseyear,
                include_base_year=False,
                flows={
                    'bottom_up': bu_eol_df,
                    'residual': residual_eol_df
                },
                fill_values_per_df={
                    'bottom_up': {'End use sector': 'Buildings', 'Region simple': 'EU28'},
                    'residual': {'End use sector': 'Residual', 'Region simple': 'EU28'}
                }
            )
            total_future_eol_df.to_csv(output_total_eol_filepath, index=False)
            print(f"Total future EOL flows gespeichert: {output_total_eol_filepath}")
            # File paths for EOL flows
            #top_down_eol_filepath = 'data/baseline_cement_stock_flows/output/export/flows/end_use_stock_future__cdw_collection_future.csv'
            #output_eol_filepath = 'data/baseline_cement_stock_flows/input/datasets/total_future_eol_flows.csv'
            #eol_data = pd.read_csv(top_down_eol_filepath)
            #eol_data.to_csv(output_eol_filepath, index=False)

        if "plastics" in materials_to_consider and downstream_only == False:
            pass
        if "steel" in materials_to_consider and downstream_only == False:
            pass

        #   g) Downstream modell rechnen
        if "concrete" in materials_to_consider:
        # calculate historic and future flows
            flows_concrete = run_eumfa("config/cement_flows.yml")


        # Combine historic and future tables


            # Combine historic and future tables (neu via flodym Helfer)
            results_folder = "data/baseline_cement_stock_flows/output/export/flows"
            historic_files = glob.glob(os.path.join(results_folder, "*historic*.csv"))
            for historic_file in historic_files:
                future_file = historic_file.replace("historic", "future")
                if os.path.exists(future_file):
                    output_file = historic_file.replace("historic", "combined")
                    try:
                        flow_calculator.combine_hist_future_flodym(
                            historic_path=historic_file,
                            future_path=future_file,
                            output_path=output_file,
                            time_col='Time',
                            value_col='value'
                        )
                        print(f"Combined table saved to: {output_file}")
                    except Exception as e:
                        print(f"Error combining (flodym) {historic_file} + {future_file}: {e}")
                else:
                    logging.warning(f"Future file not found for: {historic_file}")

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
