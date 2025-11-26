
# eumfa_combined.py

# 1. run bottom up model, extract material demand and eol flows

# 2. map dimensions (regions first, then products/materials)

# 3. read top down demand, optionally map, calculate residual demand and project

# 4. run stock model with residual demand to calculate residual eol flows

# 5. calculate total material demand and total eol flow

# 6. run with these inputs flow model

# 7. combine historic and future tables

import os
import logging
from typing import List, Dict, Optional, Tuple

import pandas as pd

from run_eumfa import run_eumfa
from src.common.combine_flows import FlowCalculator
from src.common.combine_spec import MAPPING, TOPDOWN, SOURCE_FLOWS, get_dim_catalog, products_csv_sep_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Choose material and bottom up models

use_buildings = True
use_vehicles = False
combine_plastics = False  # only possible for demand-driven
combine_steel = False     # only possible for demand-driven
combine_cement = True
downstream_only = False
baseyear = 2023

fc = FlowCalculator()

# --- Standardization helpers ---

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
            df[c] = "Buildings" if c == "End use sector" else "Unknown"
    return df

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

# --- Bottom-up remapping helpers ---

def _original_dimension_from_products_csv(path: str, sep: Optional[str] = None) -> str:
    df = pd.read_csv(path, sep=sep or None, engine="python")
    if "original_dimension" not in df.columns:
        raise ValueError(f"Missing 'original_dimension' in mapping CSV: {path}")
    return df["original_dimension"].dropna().astype(str).str.replace("\ufeff", "", regex=False).str.strip().iloc[0]

def _target_pairs_in_products_csv(path: str, sep: Optional[str] = None) -> List[Tuple[str, str]]:
    df = pd.read_csv(path, sep=sep or None, engine="python")
    dim_cols = [c for c in df.columns if c.startswith("target_dimension")]
    elem_cols = [c for c in df.columns if c.startswith("target_element")]
    dim_cols_sorted = sorted(dim_cols, key=lambda x: (x.rstrip(".0123456789"), x))
    elem_cols_sorted = sorted(elem_cols, key=lambda x: (x.rstrip(".0123456789"), x))
    return [(dim_cols_sorted[i], elem_cols_sorted[i]) for i in range(min(len(dim_cols_sorted), len(elem_cols_sorted)))]

def _map_bu_source_to_target(
    flow_df: pd.DataFrame,
    *,
    region_src_dim: str,
    region_tgt_dim: str,
    regions_csv: str,
    products_csv: str,
    target: str,  # "plastics" | "steel" | "cement"
    value_col: str = "value",
) -> pd.DataFrame:
    # Region map
    reg_mapped = fc.apply_region_map_array(
        flow_df=flow_df,
        src_dim=region_src_dim,
        tgt_dim=region_tgt_dim,
        mapping_csv=regions_csv,
        value_col=value_col,
    )
    # Products map
    sep = products_csv_sep_for(target)
    orig_dim = _original_dimension_from_products_csv(products_csv, sep=sep)
    # Clean original product strings before merge (strip BOM/whitespace)
    if orig_dim in reg_mapped.columns:
        reg_mapped[orig_dim] = (
            reg_mapped[orig_dim].astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
        )

    target_pairs = _target_pairs_in_products_csv(products_csv, sep=sep)
    dim_catalog = get_dim_catalog(target)

    mapping_df = fc.build_products_map_array(
        mapping_csv=products_csv,
        orig_dim=orig_dim,
        target_pairs=target_pairs,
        region_col=region_tgt_dim,
        dim_catalog=dim_catalog,
        sep=sep,
    )
    # Use actual mapped dimension columns created in mapping_df
    target_dims = [
        c for c in mapping_df.columns
        if c not in {orig_dim, "factor", "target_region", "target_parameter", "parameter"}
    ]

    prod_mapped = fc.apply_products_map_array(
        flow_df=reg_mapped,
        mapping_df=mapping_df,
        orig_dim=orig_dim,
        target_dims=target_dims,
        region_col=region_tgt_dim,
        value_col=value_col,
    )
    return prod_mapped

# --- Main ---

if __name__ == "__main__":
    try:
        flows_buildings: Optional[Dict[str, pd.DataFrame]] = None
        flows_vehicles: Optional[Dict[str, pd.DataFrame]] = None

        # Step 1: bottom-up models (unless downstream-only)
        if not downstream_only:
            if use_buildings:
                flows_buildings = run_eumfa("config/buildings.yml")
            if use_vehicles:
                try:
                    flows_vehicles = run_eumfa("config/vehicles.yml")
                except Exception as e:
                    logging.warning(f"Vehicles run failed: {e}")

        # Plastics
        if combine_plastics:
            if downstream_only:
                run_eumfa("config/plastics_baseline.yml")
            else:
                mapped_parts: List[pd.DataFrame] = []
                if flows_buildings:
                    df_b = flows_buildings.get(SOURCE_FLOWS.buildings_insulation)
                    if df_b is not None:
                        mapped_parts.append(
                            _std_plastics_cols(
                                _map_bu_source_to_target(
                                    flow_df=df_b.reset_index(),
                                    region_src_dim="Region",
                                    region_tgt_dim="region",
                                    regions_csv=MAPPING["buildings_plastics_regions"],
                                    products_csv=MAPPING["buildings_plastics_products"],
                                    target="plastics",
                                )
                            )
                        )
                if flows_vehicles:
                    df_v = flows_vehicles.get(SOURCE_FLOWS.vehicles_plastics)
                    if df_v is not None:
                        mapped_parts.append(
                            _std_plastics_cols(
                                _map_bu_source_to_target(
                                    flow_df=df_v.reset_index(),
                                    region_src_dim="Region",
                                    region_tgt_dim="region",
                                    regions_csv=MAPPING["vehicles_plastics_regions"],
                                    products_csv=MAPPING["vehicles_plastics_products"],
                                    target="plastics",
                                )
                            )
                        )

                bu_plastics = pd.concat(mapped_parts, ignore_index=True) if mapped_parts else pd.DataFrame(
                    columns=["time", "region", "sector", "polymer", "element", "parameter", "value"]
                )
                bu_out = os.path.join(TOPDOWN["plastics_dir"], "bottom_up_demand_all.csv")
                _ensure_dir(bu_out); bu_plastics.to_csv(bu_out, index=False)

                # Step 3: residual projection
                start_df = _std_plastics_cols(pd.read_csv(TOPDOWN["plastics_start"]))
                growth_df = _std_plastics_cols(pd.read_csv(TOPDOWN["plastics_growth"]))
                bu_df = _std_plastics_cols(pd.read_csv(bu_out))

                residual_future = fc.compute_residual_flodym(
                    start_value_df=start_df,
                    bottom_up_df=bu_df,
                    growth_rate_df=growth_df,
                    base_year=baseyear,
                    time_col="time",
                    value_col="value",
                    key_cols=("region", "sector", "polymer", "element"),
                )
                residual_out = os.path.join(TOPDOWN["plastics_dir"], "demand_future.csv")
                residual_future.rename(columns={"value": "Value"}).to_csv(residual_out, index=False)

                # Step 5: total demand
                total_future = fc.compute_total_future_flodym(
                    key_cols=("region", "sector", "polymer", "element"),
                    time_col="time",
                    value_col="value",
                    base_year=baseyear,
                    include_base_year=False,
                    flows={"bottom_up": bu_df, "residual": residual_future},
                    fill_values_per_df={"bottom_up": {"element": "All"}, "residual": {"element": "All"}},
                )
                final_demand_path = os.path.join(TOPDOWN["plastics_dir"], "FinalDemand.csv")
                total_future.rename(columns={"value": "Value"}).to_csv(final_demand_path, index=False)
                logging.info(f"[Plastics] FinalDemand written: {final_demand_path}")

                # Step 6
                run_eumfa("config/plastics_baseline.yml")

                # Step 7
                hist_fd = os.path.join(TOPDOWN["plastics_dir"], "FinalDemand_historic.csv")
                if os.path.exists(hist_fd):
                    combined_fd = os.path.join(TOPDOWN["plastics_dir"], "FinalDemand_all.csv")
                    fc.combine_hist_future_flodym(hist_fd, final_demand_path, combined_fd, time_col="time", value_col="Value", base_year=baseyear)

        # Steel
        if combine_steel:
            if downstream_only:
                run_eumfa("config/steel.yml")
            else:
                mapped_parts_steel: List[pd.DataFrame] = []
                if flows_vehicles:
                    df_vs = flows_vehicles.get(SOURCE_FLOWS.vehicles_steel)
                    if df_vs is not None:
                        mapped_parts_steel.append(
                            _std_steel_cols(
                                _map_bu_source_to_target(
                                    flow_df=df_vs.reset_index(),
                                    region_src_dim="Region",
                                    region_tgt_dim="region",
                                    regions_csv=MAPPING["vehicles_steel_regions"],
                                    products_csv=MAPPING["vehicles_steel_products"],
                                    target="steel",
                                )
                            )
                        )
                if flows_buildings:
                    df_bs = flows_buildings.get(SOURCE_FLOWS.buildings_steel)
                    if df_bs is not None:
                        mapped_parts_steel.append(
                            _std_steel_cols(
                                _map_bu_source_to_target(
                                    flow_df=df_bs.reset_index(),
                                    region_src_dim="Region",
                                    region_tgt_dim="region",
                                    regions_csv=MAPPING["buildings_steel_regions"],
                                    products_csv=MAPPING["buildings_steel_products"],
                                    target="steel",
                                )
                            )
                        )

                bu_steel = pd.concat(mapped_parts_steel, ignore_index=True) if mapped_parts_steel else pd.DataFrame(
                    columns=["time", "region", "sector", "intermediate", "product", "element", "parameter", "value"]
                )
                bu_out_s = os.path.join(TOPDOWN["steel_dir"], "bottom_up_demand_all.csv")
                _ensure_dir(bu_out_s); bu_steel.to_csv(bu_out_s, index=False)

                start_s = _std_steel_cols(pd.read_csv(TOPDOWN["steel_start"]))
                growth_s = _std_steel_cols(pd.read_csv(TOPDOWN["steel_growth"]))
                bu_s = _std_steel_cols(pd.read_csv(bu_out_s))

                residual_future_s = fc.compute_residual_flodym(
                    start_value_df=start_s,
                    bottom_up_df=bu_s,
                    growth_rate_df=growth_s,
                    base_year=baseyear,
                    time_col="time",
                    value_col="value",
                    key_cols=("region", "sector", "intermediate", "product", "element"),
                )
                residual_out_s = os.path.join(TOPDOWN["steel_dir"], "demand_future.csv")
                residual_future_s.rename(columns={"value": "Value"}).to_csv(residual_out_s, index=False)

                total_future_s = fc.compute_total_future_flodym(
                    key_cols=("region", "sector", "intermediate", "product", "element"),
                    time_col="time",
                    value_col="value",
                    base_year=baseyear,
                    include_base_year=False,
                    flows={"bottom_up": bu_s, "residual": residual_future_s},
                    fill_values_per_df={"bottom_up": {"element": "All"}, "residual": {"element": "All"}},
                )
                final_demand_path_s = os.path.join(TOPDOWN["steel_dir"], "FinalDemand.csv")
                total_future_s.rename(columns={"value": "Value"}).to_csv(final_demand_path_s, index=False)
                logging.info(f"[Steel] FinalDemand written: {final_demand_path_s}")

                run_eumfa("config/steel.yml")

                hist_fd_s = os.path.join(TOPDOWN["steel_dir"], "FinalDemand_historic.csv")
                if os.path.exists(hist_fd_s):
                    combined_fd_s = os.path.join(TOPDOWN["steel_dir"], "FinalDemand_all.csv")
                    fc.combine_hist_future_flodym(hist_fd_s, final_demand_path_s, combined_fd_s, time_col="time", value_col="Value", base_year=baseyear)

        # Cement (stock -> flows)
        if combine_cement:
            if downstream_only:
                run_eumfa("config/cement_flows.yml")
            else:
                mapped_cement_parts: List[pd.DataFrame] = []
                if flows_buildings:
                    df_cb = flows_buildings.get(SOURCE_FLOWS.buildings_concrete)
                    if df_cb is not None:
                        mapped_cement_parts.append(
                            _std_cement_cols(
                                _map_bu_source_to_target(
                                    flow_df=df_cb.reset_index(),
                                    region_src_dim="Region",
                                    region_tgt_dim="Region simple",
                                    regions_csv=MAPPING["buildings_concrete_regions"],
                                    products_csv=MAPPING["buildings_concrete_products"],
                                    target="cement",
                                )
                            )
                        )

                bu_cement = pd.concat(mapped_cement_parts, ignore_index=True) if mapped_cement_parts else pd.DataFrame(
                    columns=["Time", "Region simple", "Concrete product simple", "End use sector", "parameter", "value"]
                )
                bu_out_c = os.path.join(TOPDOWN["cement_stock_dir"], "bottom_up_demand_buildings.csv")
                _ensure_dir(bu_out_c); bu_cement.to_csv(bu_out_c, index=False)

                # Read start and growth
                start_c = pd.read_csv(TOPDOWN["cement_start"], sep=";")
                growth_c = pd.read_csv(TOPDOWN["cement_growth"], sep=";")
                # Do NOT standardize growth_c to avoid adding fake product keys
                start_c = _std_cement_cols(start_c)
                bu_c = _std_cement_cols(pd.read_csv(bu_out_c))

                # Residual projection
                demand_future_df = fc.compute_residual_flodym(
                    start_value_df=start_c,
                    bottom_up_df=bu_c,
                    growth_rate_df=growth_c,
                    base_year=baseyear,
                    time_col="Time",
                    value_col="value",
                    key_cols=("Region simple", "Concrete product simple", "End use sector"),
                )

                demand_future_path = os.path.join(TOPDOWN["cement_stock_dir"], "demand_future.csv")

                # Make sure column name matches flodym expectations

                demand_future_df.rename(columns={"value": "Value"}).to_csv(demand_future_path, index=False)
                logging.info(f"[Cement] demand_future written: {demand_future_path}")

                # Step 4: stock model (residual EoL)
                flows_cement_stock = run_eumfa("config/cement_stock.yml")

                residual_future_eol = _std_cement_cols(
                    flows_cement_stock["End use stock future => CDW collection future"].reset_index()
                )

                # Step 5 compute TOTAL = bottom_up (mapped buildings) + residual (from compute_residual_flodym)

                # bu_c is already read/mapped above; demand_future_df is the residual we saved

                total_future_df = fc.compute_total_future_flodym(
                    key_cols=("Region simple", "Concrete product simple", "End use sector"),
                    time_col="Time",
                    value_col="value",
                    base_year=baseyear,
                    include_base_year=True,
                    # TOTAL(baseyear) == start_value; future = residual projection (+ base-year bottom_up only)
                    flows={"bottom_up": bu_c, "residual": demand_future_df},
                )

                # Write TOTAL for flows model as total_future_demand.csv

                tfd_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_demand.csv")
                tfe_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_eol_flows.csv")
                _ensure_dir(tfd_path);
                _ensure_dir(tfe_path)
                total_future_df.rename(columns={"value": "Value"}).to_csv(tfd_path, index=False)
                residual_future_eol.rename(columns={"value": "Value"}).to_csv(tfe_path, index=False)
                logging.info("[Cement] total_future_demand (TOTAL) and total_future_eol_flows (RESIDUAL) written.")

                # Step 6: flows
                run_eumfa("config/cement_flows.yml")

                # Step 7: combine historic+future if available
                hist_c = os.path.join(TOPDOWN["cement_flows_dir"], "concrete_market_historic.csv")
                fut_c = os.path.join(TOPDOWN["cement_flows_dir"], "concrete_market_future.csv")
                if os.path.exists(hist_c) and os.path.exists(fut_c):
                    combined_c = os.path.join(TOPDOWN["cement_flows_dir"], "concrete_market_all.csv")
                    fc.combine_hist_future_flodym(hist_c, fut_c, combined_c, time_col="Time", value_col="Value", base_year=baseyear)

                # Quick diagnostics
                df = pd.read_csv(demand_future_path)
                print(df.head())
                print(df.groupby(["End use sector", "Concrete product simple"])["Value"].sum())

                sv = pd.read_csv(TOPDOWN["cement_start"], sep=";")
                bu = pd.read_csv(bu_out_c)
                sv23 = sv[sv["Time"] == baseyear]
                bu23 = bu[bu["Time"] == baseyear]
                cols = ["Region simple", "Concrete product simple", "End use sector"]
                sv_g = sv23.groupby(cols)["Value"].sum()
                bu_g = bu23.groupby(cols)["value"].sum()  # bottom_up still 'value' here
                res = (sv_g - bu_g).clip(lower=0).fillna(sv_g)
                print(res)

                print(pd.read_csv(demand_future_path)["End use sector"].unique())

    except Exception as e:
        logging.exception(f"eumfa_combined failed: {e}")