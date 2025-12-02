
# eumfa_combined.py

import os
import logging
from typing import List, Dict, Optional, Tuple
import glob
import pandas as pd
import re
from run_eumfa import run_eumfa
from src.common.combine_flows import FlowCalculator
from src.common.combine_spec import MAPPING, TOPDOWN, SOURCE_FLOWS, get_dim_catalog, products_csv_sep_for
from src.common.combine_flows import _filter_and_split_buildings_eol, _parse_cohort_years

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
                start_c = pd.read_csv(TOPDOWN["cement_start"])
                growth_c = pd.read_csv(TOPDOWN["cement_growth"])
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
                demand_future_df.rename(columns={"value": "Value"}).to_csv(demand_future_path, index=False)
                logging.info(f"[Cement] demand_future written: {demand_future_path}")

                # Step 4: stock model (residual EoL)
                flows_cement_stock = run_eumfa("config/cement_stock.yml")

                residual_future_eol = _std_cement_cols(
                    flows_cement_stock["End use stock future => CDW collection future"].reset_index()
                )

                # --- NEU: Buildings-EoL extrahieren, filtern, mappen ---
                if flows_buildings:
                    eol_buildings_df = flows_buildings.get("Concrete stock in buildings => sysenv")
                    if eol_buildings_df is not None:
                        eol_buildings_df = eol_buildings_df.reset_index()
                        # Kohorten korrekt filtern und aufteilen:
                        eol_buildings_df = _filter_and_split_buildings_eol(eol_buildings_df, baseyear)
                        # Mapping auf Ziel-Dimensionen für Cement
                        mapped_eol_buildings = _map_bu_source_to_target(
                            flow_df=eol_buildings_df,
                            region_src_dim="Region",
                            region_tgt_dim="Region simple",
                            regions_csv=MAPPING["buildings_concrete_regions"],
                            products_csv=MAPPING["buildings_concrete_products"],
                            target="cement",
                            value_col="value",
                        )
                        mapped_eol_buildings = _std_cement_cols(mapped_eol_buildings)
                    else:
                        mapped_eol_buildings = pd.DataFrame(
                            columns=["Time", "Region simple", "Concrete product simple", "End use sector", "parameter", "value"]
                        )
                else:
                    mapped_eol_buildings = pd.DataFrame(
                        columns=["Time", "Region simple", "Concrete product simple", "End use sector", "parameter", "value"]
                    )

                # --- TOTAL future EoL = mapped buildings + residual ---
                total_future_eol_flows = fc.compute_total_future_flodym(
                    key_cols=("Region simple", "Concrete product simple", "End use sector"),
                    time_col="Time",
                    value_col="value",
                    base_year=baseyear,
                    include_base_year=True,
                    flows={
                        "buildings_eol": mapped_eol_buildings,
                        "residual": residual_future_eol
                    }
                )

                # Step 5: total demand wie gehabt
                total_future_df = fc.compute_total_future_flodym(
                    key_cols=("Region simple", "Concrete product simple", "End use sector"),
                    time_col="Time",
                    value_col="value",
                    base_year=baseyear,
                    include_base_year=True,
                    flows={"bottom_up": bu_c, "residual": demand_future_df},
                )

                # Write TOTAL for flows model as total_future_demand.csv und total_future_eol_flows.csv
                tfd_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_demand.csv")
                tfe_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_eol_flows.csv")
                _ensure_dir(tfd_path)
                _ensure_dir(tfe_path)
                total_future_df.rename(columns={"value": "Value"}).to_csv(tfd_path, index=False)
                total_future_eol_flows.rename(columns={"value": "Value"}).to_csv(tfe_path, index=False)
                logging.info("[Cement] total_future_demand (TOTAL) and total_future_eol_flows (TOTAL = buildings+residual, cohorts handled) written.")

                # Step 6: flows
                run_eumfa("config/cement_flows.yml")

                # Step 7: combine all historic+future files with matching names



                flows_dir = os.path.join(
                    os.path.dirname(TOPDOWN["cement_flows_dir"]),
                    "..", "output", "export", "flows"
                )
                flows_dir = os.path.normpath(flows_dir)

                all_files = glob.glob(os.path.join(flows_dir, "*.csv"))


                def normalize_key(fname):
                    # Entfernt in ALLEN Teilen _historic/_future am Ende VOR .csv
                    parts = fname.replace(".csv", "").split("__")
                    clean = []
                    for p in parts:
                        for suf in ("_historic", "_future"):
                            if p.endswith(suf):
                                p = p[: -len(suf)]
                        clean.append(p)
                    return "__".join(clean)


                flow_pairs = {}
                for file in all_files:
                    fname = os.path.basename(file)
                    base_key = normalize_key(fname)
                    if fname.endswith("_historic.csv"):
                        flow_pairs.setdefault(base_key, {})["historic"] = file
                    elif fname.endswith("_future.csv"):
                        flow_pairs.setdefault(base_key, {})["future"] = file

                for key, pair in flow_pairs.items():
                    print(f"{key}: {list(pair.keys())}")  # Debug!
                    if "historic" in pair and "future" in pair:
                        out_path = os.path.join(flows_dir, f"{key}_all.csv")
                        print(f"Kombiniere: {pair['historic']} + {pair['future']} -> {out_path}")
                        fc.combine_hist_future_flodym(
                            pair["historic"],
                            pair["future"],
                            out_path,
                            time_col="Time",
                            value_col="value",
                            base_year=baseyear
                        )
                        logging.info(f"[Cement] Combined written: {out_path}")


    except Exception as e:
        logging.exception(f"eumfa_combined failed: {e}")