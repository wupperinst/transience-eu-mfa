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

fc = FlowCalculator()

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

"""Choose material and bottom up models"""
use_buildings = True
use_vehicles = True
combine_plastics = True  #only possible for demand driven
combine_steel = False #only possible for demand driven
combine_cement = True
downstream_only = False # uses given demand and eol flows and calculates recycling rate, production...
baseyear = 2023

#file paths for mapping
mapping_file_path_buildings_concrete = "data/baseline_combined/mapping_buildings_concrete.csv"
mapping_file_path_buildings_steel = "data/baseline_combined/mapping_buildings_steel.csv"
mapping_file_path_buildings_plastics = "data/baseline_combined/mapping_buildings_plastics.csv"
mapping_file_path_vehicles_steel = "data/baseline_combined/mapping_vehicles_steel.csv"
mapping_file_path_vehicles_plastics = "data/baseline_combined/mapping_vehicles_plastics.csv"

#file paths and files for top-down results
plastics_topdown_dir = "data/baseline_plastics_flows/input/datasets"
steel_topdown_dir    = "data/baseline_steel_flows/input/datasets"
cement_stock_dir     = "data/baseline_cement_stock/input/datasets"
cement_flows_dir     = "data/baseline_cement_flows/input/datasets"
plastics_start_value_csv = os.path.join(plastics_topdown_dir, "start_value.csv")
plastics_growth_rate_csv = os.path.join(plastics_topdown_dir, "growth_rate.csv")
steel_start_value_csv = os.path.join(steel_topdown_dir, "start_value.csv")
steel_growth_rate_csv = os.path.join(steel_topdown_dir, "growth_rate.csv")
cement_start_value_csv = os.path.join(cement_flows_dir, "start_value.csv")
cement_growth_rate_csv = os.path.join(cement_flows_dir, "growth_rate.csv")

#Supporting functions
def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _std_plastics_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "Time": "time", "Region": "region", "Sector": "sector",
        "Polymer": "polymer", "Element": "element",
    }, errors="ignore")
    for c in ("time", "region", "sector", "polymer"):
        if c not in df.columns:
            df[c] = "Unknown"
    if "element" not in df.columns:
        df["element"] = "All"
    return df

def _std_steel_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "Time": "time", "Region": "region", "Sector": "sector",
        "Intermediate": "intermediate", "Product": "product", "Element": "element",
    }, errors="ignore")
    for c in ("time", "region", "sector", "intermediate", "product"):
        if c not in df.columns:
            df[c] = "Unknown"
    if "element" not in df.columns:
        df["element"] = "All"
    return df

def _std_cement_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "Time": "Time", "Region": "Region simple",
        "Concrete product": "Concrete product simple",
        "End use sector": "End use sector",
    }, errors="ignore")
    for c in ("Time", "Region simple", "Concrete product simple", "End use sector"):
        if c not in df.columns:
            # Default: fehlende Dimensionen mit sinnvollen Werten auffüllen
            if c == "End use sector":
                df[c] = "Buildings"
            else:
                df[c] = "Unknown"
    return df

def _map_bottom_up_to_target(flows: dict, relevant_flows: list[str], mapping_csv: str, std_fn) -> list[pd.DataFrame]:
    out = []
    if flows is None:
        return out
    mapping_df = pd.read_csv(mapping_csv, sep=None, engine="python")
    for flow_name, flow in flows.items():
        if flow_name not in relevant_flows:
            continue
        fdf = flow.to_df().reset_index() if hasattr(flow, "to_df") else flow.copy()
        remapped = fc.map_dimensions_dual_targets(
            original_df=fdf,
            mapping_df=mapping_df,
            value_col="value",
            drop_source_dims=True,
        )
        out.append(std_fn(remapped))
    return out

def _concat_and_keep(df_list: list[pd.DataFrame], cols: list[str]) -> pd.DataFrame:
    if not df_list:
        raise RuntimeError("Keine passenden Bottom-up-Flows gefunden.")
    df = pd.concat(df_list, ignore_index=True)
    return df[cols].copy()

#Sub-module combination
if __name__ == "__main__":
    try:
        flows_buildings = None
        flows_vehicles = None

        if use_buildings and not downstream_only:
            flows_buildings = run_eumfa("config/buildings.yml")
        if use_vehicles and not downstream_only:
            flows_vehicles = run_eumfa("config/vehicles.yml")

        #Combination of bottom-up sub-modules with plastics
        if combine_plastics and not downstream_only:
            mapped_parts = []
            mapped_parts += _map_bottom_up_to_target(
                flows=flows_buildings,
                relevant_flows=["sysenv => Insulation stock in buildings"],
                mapping_csv=mapping_file_path_buildings_plastics,
                std_fn=_std_plastics_cols,
            )
            mapped_parts += _map_bottom_up_to_target(
                flows=flows_vehicles,
                relevant_flows=["sysenv => Plastics stock in vehicles"],
                mapping_csv=mapping_file_path_vehicles_plastics,
                std_fn=_std_plastics_cols,
            )

            bu_demand_plastics = _concat_and_keep(
                mapped_parts, ["time", "region", "sector", "polymer", "element", "value"]
            )
            bu_path = os.path.join(plastics_topdown_dir, "bottom_up_demand_all.csv")
            _ensure_dir(bu_path)
            bu_demand_plastics.to_csv(bu_path, index=False)

            start_df = _std_plastics_cols(pd.read_csv(plastics_start_value_csv))
            growth_df = _std_plastics_cols(pd.read_csv(plastics_growth_rate_csv))
            bu_df = _std_plastics_cols(pd.read_csv(bu_path))

            residual_future = fc.compute_residual_flodym(
                start_value_df=start_df,
                bottom_up_df=bu_df,
                growth_rate_df=growth_df,
                base_year=baseyear,
                time_col="time",
                value_col="value",
                key_cols=("region", "sector", "polymer", "element"),
            )
            residual_out = os.path.join(plastics_topdown_dir, "demand_future.csv")
            residual_future.to_csv(residual_out, index=False)

            total_future = fc.compute_total_future_flodym(
                key_cols=("region", "sector", "polymer", "element"),
                time_col="time",
                value_col="value",
                base_year=baseyear,
                include_base_year=False,
                flows={"bottom_up": bu_df, "residual": residual_future},
                fill_values_per_df={"bottom_up": {"element": "All"}, "residual": {"element": "All"}},
            )
            final_demand_path = os.path.join(plastics_topdown_dir, "FinalDemand.csv")
            total_future.to_csv(final_demand_path, index=False)
            print(f"[Plastics] FinalDemand: {final_demand_path}")

            run_eumfa("config/plastics_baseline.yml")

        #Combination of bottom-up sub-modules with steel
        if combine_steel and not downstream_only:
            mapped_parts_steel = []
            mapped_parts_steel += _map_bottom_up_to_target(
                flows=flows_buildings,
                relevant_flows=["sysenv => Steel stock in buildings"],
                mapping_csv=mapping_file_path_buildings_steel,
                std_fn=_std_steel_cols,
            )
            mapped_parts_steel += _map_bottom_up_to_target(
                flows=flows_vehicles,
                relevant_flows=["sysenv => Steel stock in vehicles"],
                mapping_csv=mapping_file_path_vehicles_steel,
                std_fn=_std_steel_cols,
            )

            bu_demand_steel = _concat_and_keep(
                mapped_parts_steel, ["time", "region", "sector", "intermediate", "product", "element", "value"]
            )
            bu_path_steel = os.path.join(steel_topdown_dir, "bottom_up_demand_all.csv")
            _ensure_dir(bu_path_steel)
            bu_demand_steel.to_csv(bu_path_steel, index=False)

            start_df_s = _std_steel_cols(pd.read_csv(steel_start_value_csv))
            growth_df_s = _std_steel_cols(pd.read_csv(steel_growth_rate_csv))
            bu_df_s = _std_steel_cols(pd.read_csv(bu_path_steel))

            residual_future_s = fc.compute_residual_flodym(
                start_value_df=start_df_s,
                bottom_up_df=bu_df_s,
                growth_rate_df=growth_df_s,
                base_year=baseyear,
                time_col="time",
                value_col="value",
                key_cols=("region", "sector", "intermediate", "product", "element"),
            )
            residual_out_s = os.path.join(steel_topdown_dir, "demand_future.csv")
            residual_future_s.to_csv(residual_out_s, index=False)

            total_future_s = fc.compute_total_future_flodym(
                key_cols=("region", "sector", "intermediate", "product", "element"),
                time_col="time", value_col="value", base_year=baseyear, include_base_year=False,
                flows={"bottom_up": bu_df_s, "residual": residual_future_s},
                fill_values_per_df={"bottom_up": {"element": "All"}, "residual": {"element": "All"}},
            )
            final_demand_path = os.path.join(steel_topdown_dir, "FinalDemand.csv")
            total_future_s.to_csv(final_demand_path, index=False)
            print(f"[Steel] FinalDemand: {final_demand_path}")

            run_eumfa("config/steel.yml")

        #Combination of bottom-up sub-modules with cement
        if combine_cement and use_buildings and not downstream_only:
            mapped_cement_parts = _map_bottom_up_to_target(
                flows=flows_buildings,
                relevant_flows=["sysenv => Concrete stock in buildings"],
                mapping_csv=mapping_file_path_buildings_concrete,
                std_fn=_std_cement_cols,
            )
            bu_demand_cement = _concat_and_keep(
                mapped_cement_parts,
                ["Time", "Region simple", "Concrete product simple", "End use sector", "value"],
            )
            bu_path_cement = os.path.join(cement_stock_dir, "bottom_up_demand_buildings.csv")
            _ensure_dir(bu_path_cement)
            bu_demand_cement.to_csv(bu_path_cement, index=False)

            start_df_c = _std_cement_cols(pd.read_csv(cement_start_value_csv))
            growth_df_c = _std_cement_cols(pd.read_csv(cement_growth_rate_csv))
            bu_df_c = _std_cement_cols(pd.read_csv(bu_path_cement))

            demand_future_df = fc.compute_residual_flodym(
                start_value_df=start_df_c,
                bottom_up_df=bu_df_c,
                growth_rate_df=growth_df_c,
                base_year=baseyear,
                time_col="Time",
                value_col="value",
                key_cols=("Region simple", "Concrete product simple", "End use sector"),
            )
            demand_future_path = os.path.join(cement_stock_dir, "demand_future.csv")
            demand_future_df.to_csv(demand_future_path, index=False)
            print(f"[Cement] demand_future: {demand_future_path}")

            run_eumfa("config/cement_stock.yml")

            # total_future_demand/eol aus cement_stock-Export ziehen und an cement_flows übergeben
            # Dateinamen gemäß sanitize_filename:
            from src.common.combine_flows import FlowCalculator as FC
            inflow_export = os.path.join(
                os.path.dirname(cement_stock_dir.replace("/input", "/output")),
                "export", "flows",
                f"{FC.sanitize_filename('Concrete market future => End use stock future')}.csv",
            )
            eol_export = os.path.join(
                os.path.dirname(cement_stock_dir.replace("/input", "/output")),
                "export", "flows",
                f"{FC.sanitize_filename('End use stock future => CDW collection future')}.csv",
            )
            total_future_demand = pd.read_csv(inflow_export)
            total_future_eol = pd.read_csv(eol_export)

            # Sicherstellen, dass Spaltennamen mit cement_flows übereinstimmen
            total_future_demand = _std_cement_cols(total_future_demand)
            total_future_eol = _std_cement_cols(total_future_eol)

            tfd_path = os.path.join(cement_flows_dir, "total_future_demand.csv")
            tfe_path = os.path.join(cement_flows_dir, "total_future_eol_flows.csv")
            _ensure_dir(tfd_path); _ensure_dir(tfe_path)
            total_future_demand.to_csv(tfd_path, index=False)
            total_future_eol.to_csv(tfe_path, index=False)
            print(f"[Cement] total_future_demand/eol geschrieben: {tfd_path} | {tfe_path}")

            # e) cement_flows laufen lassen (nutzt total_future_* als Input)
            run_eumfa("config/cement_flows.yml")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pass
