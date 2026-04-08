# eumfa_combined.py

"""
EU MFA Combined Model - Main Orchestration Script

This script integrates bottom-up sectoral models (Buildings, Vehicles) with
top-down material flow models (Plastics, Steel, Cement).

The combination approach:
1. Runs bottom-up models to get detailed sectoral material demand
2. Maps bottom-up flows to top-down model dimensions
3. Calculates residual demand (top-down - bottom-up)
4. Projects residual using growth rates
5. Runs historic and future material models
6. Combines results into unified output files

Usage:
    python eumfa_combined.py

Configuration flags at the top of the file control which models run.
"""

import glob
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm

from run_eumfa import run_eumfa
from src.common.combine_flows import FlowCalculator, _filter_and_split_buildings_eol
from src.common.combine_spec import (
    MAPPING,
    TOPDOWN,
    SOURCE_FLOWS,
    PLASTICS_AUTO_SECTOR,
    get_dim_catalog,
    get_plastics_config,
)

# =============================================================================

# CONFIGURATION

# =============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- Model Selection Flags ---

USE_BUILDINGS = False
USE_VEHICLES = True
COMBINE_PLASTICS = True
COMBINE_STEEL = False
COMBINE_CEMENT = False
DOWNSTREAM_ONLY = False
BASE_YEAR = 2023

# Global FlowCalculator instance

fc = FlowCalculator()


# =============================================================================

# COLUMN STANDARDIZATION HELPERS

# =============================================================================


def std_plastics_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names for plastics model."""
    df = df.rename(
        columns={
            "Time": "time",
            "Region": "region",
            "Sector": "sector",
            "Polymer": "polymer",
            "Element": "element",
        },
        errors="ignore",
    )
    for c in ("time", "region", "sector", "polymer"):
        if c not in df.columns:
            df[c] = "Unknown"
    if "element" not in df.columns:
        df["element"] = "All"
    return df


def std_steel_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names for steel model."""
    df = df.rename(
        columns={
            "Time": "time",
            "Region": "region",
            "Sector": "sector",
            "Intermediate": "intermediate",
            "Product": "product",
            "Element": "element",
        },
        errors="ignore",
    )
    for c in ("time", "region", "sector", "intermediate", "product"):
        if c not in df.columns:
            df[c] = "Unknown"
    if "element" not in df.columns:
        df["element"] = "All"
    return df


def std_cement_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names for cement model."""
    df = df.rename(
        columns={
            "Time": "Time",
            "Region": "Region simple",
            "Concrete product": "Concrete product simple",
            "End use sector": "End use sector",
        },
        errors="ignore",
    )
    for c in ("Time", "Region simple", "Concrete product simple", "End use sector"):
        if c not in df.columns:
            df[c] = "Buildings" if c == "End use sector" else "Unknown"
    return df


def ensure_dir(path: str) -> None:
    """Ensure directory exists for a file path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


# =============================================================================

# MAPPING HELPERS

# =============================================================================


def get_original_dimension_from_csv(path: str, sep: Optional[str] = None) -> str:
    """Extract original_dimension value from mapping CSV."""
    df = pd.read_csv(path, sep=sep or None, engine="python")
    if "original_dimension" not in df.columns:
        raise ValueError(f"Missing 'original_dimension' in: {path}")
    return (
        df["original_dimension"]
        .dropna()
        .astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .iloc[0]
    )


def get_target_pairs_from_csv(
    path: str, sep: Optional[str] = None
) -> List[Tuple[str, str]]:
    """Extract target dimension/element column pairs from mapping CSV."""
    df = pd.read_csv(path, sep=sep or None, engine="python")
    dim_cols = sorted([c for c in df.columns if c.startswith("target_dimension")])
    elem_cols = sorted([c for c in df.columns if c.startswith("target_element")])
    return list(zip(dim_cols[: len(elem_cols)], elem_cols[: len(dim_cols)]))


def map_bottom_up_to_target(
    flow_df: pd.DataFrame,
    *,
    region_src_dim: str,
    region_tgt_dim: str,
    regions_csv: str,
    products_csv: str,
    target: str,
    value_col: str = "value",
) -> pd.DataFrame:
    """
    Map bottom-up flow to target model dimensions.

    Applies region mapping followed by product mapping.

    Parameters
    ----------
    flow_df : DataFrame
        Source flow data
    region_src_dim : str
        Source region column name (e.g., "Region")
    region_tgt_dim : str
        Target region column name (e.g., "region")
    regions_csv : str
        Path to region mapping CSV
    products_csv : str
        Path to products mapping CSV
    target : str
        Target model name for dimension catalog lookup
    value_col : str
        Name of value column

    Returns
    -------
    DataFrame
        Mapped flow data with target dimensions
    """
    # Apply region mapping
    reg_mapped = fc.apply_region_map_array(
        flow_df=flow_df,
        src_dim=region_src_dim,
        tgt_dim=region_tgt_dim,
        mapping_csv=regions_csv,
        value_col=value_col,
    )

    # Get product mapping configuration
    sep = ","
    orig_dim = get_original_dimension_from_csv(products_csv, sep=sep)
    target_pairs = get_target_pairs_from_csv(products_csv, sep=sep)
    dim_catalog = get_dim_catalog(target)

    # Clean original dimension values
    if orig_dim in reg_mapped.columns:
        reg_mapped[orig_dim] = (
            reg_mapped[orig_dim]
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
        )

    # Build and apply product mapping
    mapping_df = fc.build_products_map_array(
        mapping_csv=products_csv,
        orig_dim=orig_dim,
        target_pairs=target_pairs,
        region_col=region_tgt_dim,
        dim_catalog=dim_catalog,
        sep=sep,
    )

    target_dims = [
        c
        for c in mapping_df.columns
        if c
        not in {orig_dim, "factor", "target_region", "target_parameter", "parameter"}
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


def aggregate_vehicle_type(df: pd.DataFrame, value_col: str = "value") -> pd.DataFrame:
    """Aggregate flow DataFrame over Vehicle type dimension."""
    if "Vehicle type" not in df.columns:
        return df
    group_cols = [c for c in df.columns if c not in ["Vehicle type", value_col]]
    return df.groupby(group_cols, as_index=False)[value_col].sum()


def map_vehicles_to_plastics(
    flow_df: pd.DataFrame,
    *,
    regions_csv: str,
    products_csv: str,
    value_col: str = "value",
) -> pd.DataFrame:
    """
    Map vehicles plastics flow to plastics model dimensions.

    Aggregates over Vehicle type, then applies region and product mapping.
    """
    df = flow_df.copy()

    # Standardize value column
    if value_col not in df.columns and "Value" in df.columns:
        df = df.rename(columns={"Value": value_col})

    # Aggregate over Vehicle type first
    df = aggregate_vehicle_type(df, value_col=value_col)

    # Apply standard mapping
    return map_bottom_up_to_target(
        flow_df=df,
        region_src_dim="Region",
        region_tgt_dim="region",
        regions_csv=regions_csv,
        products_csv=products_csv,
        target="plastics_fd_sv_gr",
        value_col=value_col,
    )


# =============================================================================

# EOL CALCULATION HELPERS

# =============================================================================


def compute_residual_eol_inline(
    residual_demand_df: pd.DataFrame,
    lifetime_df: pd.DataFrame,
    *,
    time_col: str = "time",
    value_col: str = "value",
    base_year: int,
    max_year: int,
) -> pd.DataFrame:
    """
    Calculate EOL flows from residual demand using simplified DSM.

    Uses normal distribution survival function with std = 30% of mean lifetime.

    Parameters
    ----------
    residual_demand_df : DataFrame
        Residual demand with columns [time, region, sector, polymer, element, value]
    lifetime_df : DataFrame
        Lifetime data with columns [region, sector, polymer, value]
    time_col : str
        Name of time column
    value_col : str
        Name of value column
    base_year : int
        Base year (e.g., 2023)
    max_year : int
        Maximum projection year (e.g., 2050)

    Returns
    -------
    DataFrame
        EOL flows with columns [time, age-cohort, region, sector, polymer, element, value]
    """
    results = []

    # Prepare demand data
    demand_df = residual_demand_df.copy()
    if value_col not in demand_df.columns and "Value" in demand_df.columns:
        demand_df = demand_df.rename(columns={"Value": value_col})
    demand_df[value_col] = pd.to_numeric(demand_df[value_col], errors="coerce").fillna(
        0
    )

    # Prepare lifetime data
    lt_df = lifetime_df.copy()
    for alt in ["value", "Value", "mean", "Mean"]:
        if alt in lt_df.columns:
            lt_df = lt_df.rename(columns={alt: "lt_value"})
            break

    if "lt_value" not in lt_df.columns:
        raise ValueError(f"Lifetime DataFrame missing value column")
    lt_df["lt_value"] = pd.to_numeric(lt_df["lt_value"], errors="coerce").fillna(35.0)

    # Group by dimensions
    dim_cols = [c for c in ["region", "sector", "polymer"] if c in demand_df.columns]

    if dim_cols:
        grouped = demand_df.groupby(dim_cols)
    else:
        grouped = [(None, demand_df)]

    for key_vals, group in grouped:
        key_dict = _parse_key_dict(key_vals, dim_cols)

        # Get lifetime for this combination
        lt_mean = _get_lifetime_for_key(lt_df, key_dict, default=35.0)
        lt_std = lt_mean * 0.3

        # Calculate outflows for each cohort
        inflows = group.groupby(time_col)[value_col].sum()

        for cohort_year, inflow_val in inflows.items():
            cohort_year = int(cohort_year)
            if inflow_val <= 0:
                continue

            for year in range(cohort_year, max_year + 1):
                age = year - cohort_year
                sf_age = 1 - norm.cdf(age, loc=lt_mean, scale=lt_std)
                sf_age_next = 1 - norm.cdf(age + 1, loc=lt_mean, scale=lt_std)
                outflow = inflow_val * max(0, sf_age - sf_age_next)

                if outflow > 1e-9:
                    row = dict(key_dict)
                    row[time_col] = year
                    row["age-cohort"] = cohort_year
                    row["element"] = "All"
                    row[value_col] = outflow
                    results.append(row)

    if not results:
        return pd.DataFrame(
            columns=[
                time_col,
                "age-cohort",
                "region",
                "sector",
                "polymer",
                "element",
                value_col,
            ]
        )

    return pd.DataFrame(results)


def _parse_key_dict(key_vals, dim_cols: List[str]) -> Dict:
    """Parse groupby key values into a dictionary."""
    if key_vals is None:
        return {}
    elif isinstance(key_vals, str):
        return {dim_cols[0]: key_vals}
    else:
        return dict(zip(dim_cols, key_vals))


def _get_lifetime_for_key(
    lt_df: pd.DataFrame, key_dict: Dict, default: float = 35.0
) -> float:
    """Get lifetime value for a key combination."""
    lt_mask = pd.Series(True, index=lt_df.index)
    for k, v in key_dict.items():
        if k in lt_df.columns:
            lt_mask &= lt_df[k] == v

    lt_rows = lt_df[lt_mask]

    # Fallback: try without region
    if lt_rows.empty and "region" in key_dict:
        lt_mask = pd.Series(True, index=lt_df.index)
        for k, v in key_dict.items():
            if k in lt_df.columns and k != "region":
                lt_mask &= lt_df[k] == v
        lt_rows = lt_df[lt_mask]

    return lt_rows["lt_value"].iloc[0] if not lt_rows.empty else default


def aggregate_eol_no_cohort(df: pd.DataFrame, value_col: str = "value") -> pd.DataFrame:
    """Aggregate EOL DataFrame, removing cohort dimension."""
    if df.empty:
        return df
    group_cols = [c for c in df.columns if c not in [value_col, "age-cohort"]]
    return df.groupby(group_cols, as_index=False)[value_col].sum()


# =============================================================================

# PLASTICS MODEL HELPERS

# =============================================================================


def extract_eol_flow_memory_efficient(
    mfa_model,
    flow_name: str = "End use stock => Waste collection",
    base_year: int = 2023,
    sector_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Extract EOL flow from plastics model with memory-efficient approach.

    Iterates over dimensions to avoid memory errors from large arrays.
    Filters to cohort < base_year AND time >= base_year.

    Parameters
    ----------
    mfa_model : PlasticsModel
        The plastics model instance
    flow_name : str
        Name of the EOL flow
    base_year : int
        Base year for filtering
    sector_filter : str, optional
        Filter to specific sector

    Returns
    -------
    DataFrame
        EOL flows with cohort information
    """
    if flow_name not in mfa_model.mfa.flows:
        logging.warning(f"Flow '{flow_name}' not found in model")
        return pd.DataFrame()

    flow = mfa_model.mfa.flows[flow_name]
    dims = mfa_model.mfa.dims

    # Get dimension items
    time_items = list(dims["t"].items)
    cohort_items = list(dims["c"].items)
    region_items = list(dims["r"].items)
    sector_items = list(dims["s"].items)
    polymer_items = list(dims["p"].items)
    element_items = list(dims["e"].items) if "e" in dims else ["All"]

    # Filter indices
    time_mask = [i for i, t in enumerate(time_items) if t >= base_year]
    cohort_mask = [i for i, c in enumerate(cohort_items) if c < base_year]

    if not time_mask or not cohort_mask:
        return pd.DataFrame()

    sector_mask = (
        [i for i, s in enumerate(sector_items) if s == sector_filter]
        if sector_filter
        else list(range(len(sector_items)))
    )

    results = []

    for r_idx, region in enumerate(region_items):
        for s_idx in sector_mask:
            sector = sector_items[s_idx]
            for p_idx, polymer in enumerate(polymer_items):
                for e_idx, element in enumerate(
                    element_items if "e" in dims else ["All"]
                ):
                    for t_idx in time_mask:
                        for c_idx in cohort_mask:
                            try:
                                if "e" in dims:
                                    val = flow.values[
                                        t_idx, c_idx, r_idx, s_idx, p_idx, e_idx
                                    ]
                                else:
                                    val = flow.values[t_idx, c_idx, r_idx, s_idx, p_idx]

                                if val > 1e-9:
                                    results.append(
                                        {
                                            "time": time_items[t_idx],
                                            "age-cohort": cohort_items[c_idx],
                                            "region": region,
                                            "sector": sector,
                                            "polymer": polymer,
                                            "element": element
                                            if "e" in dims
                                            else "All",
                                            "value": val,
                                        }
                                    )
                            except IndexError:
                                continue

    if not results:
        return pd.DataFrame(
            columns=[
                "time",
                "age-cohort",
                "region",
                "sector",
                "polymer",
                "element",
                "value",
            ]
        )

    return pd.DataFrame(results)


# =============================================================================

# CEMENT COUPLING

# =============================================================================


def run_cement_coupling(flows_buildings: Optional[Dict]) -> None:
    """
    Run cement + buildings coupling.

    Steps:
    1. Map buildings concrete flows to cement dimensions
    2. Calculate residual demand
    3. Run cement stock model
    4. Extract EOL flows
    5. Run cement flows model
    6. Combine historic + future outputs

    """
    logging.info("=" * 60)
    logging.info("STARTING CEMENT + BUILDINGS COUPLING")
    logging.info("=" * 60)

    if DOWNSTREAM_ONLY:
        run_eumfa("config/cement_flows.yml")
        return

    # -------------------------------------------------------------------------
    # Step 1: Map buildings concrete to cement dimensions
    # -------------------------------------------------------------------------
    mapped_cement_parts: List[pd.DataFrame] = []

    if flows_buildings:
        df_concrete = flows_buildings.get(SOURCE_FLOWS.buildings_concrete)
        if df_concrete is not None:
            mapped = map_bottom_up_to_target(
                flow_df=df_concrete.reset_index(),
                region_src_dim="Region",
                region_tgt_dim="Region simple",
                regions_csv=MAPPING["buildings_concrete_regions"],
                products_csv=MAPPING["buildings_concrete_products"],
                target="cement",
            )
            mapped_cement_parts.append(std_cement_cols(mapped))

    bu_cement = (
        pd.concat(mapped_cement_parts, ignore_index=True)
        if mapped_cement_parts
        else pd.DataFrame(
            columns=[
                "Time",
                "Region simple",
                "Concrete product simple",
                "End use sector",
                "parameter",
                "value",
            ]
        )
    )

    # Save bottom-up demand
    bu_out_path = os.path.join(
        TOPDOWN["cement_stock_dir"], "bottom_up_demand_buildings.csv"
    )
    ensure_dir(bu_out_path)
    bu_cement.to_csv(bu_out_path, index=False)
    logging.info(f"[Cement] Bottom-up demand saved: {bu_out_path}")

    # -------------------------------------------------------------------------
    # Step 2: Calculate residual demand
    # -------------------------------------------------------------------------
    start_c = std_cement_cols(pd.read_csv(TOPDOWN["cement_start"]))
    growth_c = pd.read_csv(TOPDOWN["cement_growth"])
    bu_c = std_cement_cols(pd.read_csv(bu_out_path))

    demand_future_df = fc.compute_residual_flodym(
        start_value_df=start_c,
        bottom_up_df=bu_c,
        growth_rate_df=growth_c,
        base_year=BASE_YEAR,
        time_col="Time",
        value_col="value",
        key_cols=("Region simple", "Concrete product simple", "End use sector"),
    )

    demand_future_path = os.path.join(TOPDOWN["cement_stock_dir"], "demand_future.csv")
    demand_future_df.rename(columns={"value": "Value"}).to_csv(
        demand_future_path, index=False
    )
    logging.info(f"[Cement] Residual demand saved: {demand_future_path}")

    # -------------------------------------------------------------------------
    # Step 3: Run stock model
    # -------------------------------------------------------------------------
    flows_cement_stock = run_eumfa("config/cement_stock.yml")

    residual_future_eol = std_cement_cols(
        flows_cement_stock[
            "End use stock future => CDW collection future"
        ].reset_index()
    )

    # -------------------------------------------------------------------------
    # Step 4: Process buildings EOL
    # -------------------------------------------------------------------------
    if flows_buildings:
        eol_buildings_df = flows_buildings.get("Concrete stock in buildings => sysenv")
        if eol_buildings_df is not None:
            eol_buildings_df = eol_buildings_df.reset_index()
            eol_buildings_df = _filter_and_split_buildings_eol(
                eol_buildings_df, BASE_YEAR
            )

            mapped_eol_buildings = map_bottom_up_to_target(
                flow_df=eol_buildings_df,
                region_src_dim="Region",
                region_tgt_dim="Region simple",
                regions_csv=MAPPING["buildings_concrete_regions"],
                products_csv=MAPPING["buildings_concrete_products"],
                target="cement",
                value_col="value",
            )
            mapped_eol_buildings = std_cement_cols(mapped_eol_buildings)
        else:
            mapped_eol_buildings = pd.DataFrame(
                columns=[
                    "Time",
                    "Region simple",
                    "Concrete product simple",
                    "End use sector",
                    "parameter",
                    "value",
                ]
            )
    else:
        mapped_eol_buildings = pd.DataFrame(
            columns=[
                "Time",
                "Region simple",
                "Concrete product simple",
                "End use sector",
                "parameter",
                "value",
            ]
        )

    # -------------------------------------------------------------------------
    # Step 5: Calculate totals and run flows model
    # -------------------------------------------------------------------------
    total_future_eol_flows = fc.compute_total_future_flodym(
        key_cols=("Region simple", "Concrete product simple", "End use sector"),
        time_col="Time",
        value_col="value",
        base_year=BASE_YEAR,
        include_base_year=True,
        flows={"buildings_eol": mapped_eol_buildings, "residual": residual_future_eol},
    )

    total_future_df = fc.compute_total_future_flodym(
        key_cols=("Region simple", "Concrete product simple", "End use sector"),
        time_col="Time",
        value_col="value",
        base_year=BASE_YEAR,
        include_base_year=True,
        flows={"bottom_up": bu_c, "residual": demand_future_df},
    )

    # Save totals
    tfd_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_demand.csv")
    tfe_path = os.path.join(TOPDOWN["cement_flows_dir"], "total_future_eol_flows.csv")
    ensure_dir(tfd_path)
    ensure_dir(tfe_path)
    total_future_df.rename(columns={"value": "Value"}).to_csv(tfd_path, index=False)
    total_future_eol_flows.rename(columns={"value": "Value"}).to_csv(
        tfe_path, index=False
    )
    logging.info("[Cement] Total future demand and EOL saved")

    # Run flows model
    run_eumfa("config/cement_flows.yml")

    # -------------------------------------------------------------------------
    # Step 6: Combine historic + future outputs
    # -------------------------------------------------------------------------
    _combine_cement_flows()

    logging.info("[Cement] Coupling complete!")


def _combine_cement_flows() -> None:
    """Combine historic and future cement flow files."""
    flows_dir = os.path.join(
        os.path.dirname(TOPDOWN["cement_flows_dir"]), "..", "output", "export", "flows"
    )
    flows_dir = os.path.normpath(flows_dir)

    all_files = glob.glob(os.path.join(flows_dir, "*.csv"))

    def normalize_key(fname):
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
        if "historic" in pair and "future" in pair:
            out_path = os.path.join(flows_dir, f"{key}_all.csv")
            fc.combine_hist_future_flodym(
                pair["historic"],
                pair["future"],
                out_path,
                time_col="Time",
                value_col="value",
                base_year=BASE_YEAR,
            )
            logging.info(f"[Cement] Combined: {key}")


# =============================================================================

# PLASTICS COUPLING

# =============================================================================


def run_plastics_coupling(
    flows_buildings: Optional[Dict],
    flows_vehicles: Optional[Dict],
) -> None:
    """
    Run plastics + buildings + vehicles coupling.

    Steps:
    0. Map bottom-up flows to plastics dimensions
    1. Calculate residual demand for each sector
    2. Project residual using cumulative growth
    3. Calculate residual EOL using inline DSM
    4. Calculate total EOL flows
    5. Run historic stock model
    6. Calculate total future demand
    7. Run future flows model and combine outputs

    """
    logging.info("=" * 60)
    logging.info("STARTING PLASTICS + BUILDINGS + VEHICLES COUPLING")
    logging.info("=" * 60)

    if DOWNSTREAM_ONLY:
        logging.info("[Plastics] Running downstream-only mode")
        run_eumfa("config/plastics_fd-sv-gr.yml")
        return

    # Get configuration
    cfg = get_plastics_config()
    key_cols = cfg["key_cols"]
    time_col = cfg["time_col"]
    value_col = cfg["value_col"]
    base_year = cfg["base_year"]
    max_year = cfg["max_year"]
    bc_sector = cfg["bc_sector"]
    auto_sector = PLASTICS_AUTO_SECTOR

    logging.info(f"[Plastics] Config: base_year={base_year}, max_year={max_year}")
    logging.info(f"[Plastics] Sectors: B&C='{bc_sector}', Automotive='{auto_sector}'")

    # =========================================================================
    # STEP 0: Map bottom-up flows to plastics dimensions
    # =========================================================================
    logging.info("[Plastics] Step 0: Mapping bottom-up flows")

    # Map buildings (B&C sector)
    bu_demand_buildings, bu_eol_buildings = _map_buildings_to_plastics(
        flows_buildings, time_col, value_col, base_year
    )

    # Map vehicles (Automotive sector)
    bu_demand_vehicles, bu_eol_vehicles = _map_vehicles_to_plastics_flows(
        flows_vehicles, time_col, value_col
    )

    # Save intermediate files
    _save_plastics_intermediate_files(
        bu_demand_buildings,
        bu_eol_buildings,
        bu_demand_vehicles,
        bu_eol_vehicles,
        time_col,
        value_col,
    )

    # =========================================================================
    # Load reference data
    # =========================================================================
    start_pl = std_plastics_cols(pd.read_csv(TOPDOWN["plastics_fd_sv_gr_start"]))
    start_pl[value_col] = pd.to_numeric(start_pl[value_col], errors="coerce").fillna(0)

    growth_pl = std_plastics_cols(pd.read_csv(TOPDOWN["plastics_fd_sv_gr_growth"]))

    lifetime_pl = pd.read_csv(TOPDOWN["plastics_baseline_lifetime"])
    for col in lifetime_pl.columns:
        if col.lower() in ["value", "mean", "lifetime"]:
            lifetime_pl = lifetime_pl.rename(columns={col: "value"})
            break

    merge_keys = ["region", "sector", "polymer", "element"]

    # =========================================================================
    # STEPS 1-3: Calculate residuals for each sector
    # =========================================================================

    # B&C sector
    logging.info("[Plastics] Steps 1-3: B&C sector residual calculation")
    residual_bc_future, residual_bc_eol = _calculate_sector_residual(
        sector_name=bc_sector,
        bu_demand=bu_demand_buildings,
        start_values=start_pl,
        growth_rates=growth_pl,
        lifetime_df=lifetime_pl,
        merge_keys=merge_keys,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        max_year=max_year,
        output_prefix="bc",
    )

    # Automotive sector
    logging.info("[Plastics] Steps 1-3: Automotive sector residual calculation")
    residual_auto_future, residual_auto_eol = _calculate_sector_residual(
        sector_name=auto_sector,
        bu_demand=bu_demand_vehicles,
        start_values=start_pl,
        growth_rates=growth_pl,
        lifetime_df=lifetime_pl,
        merge_keys=merge_keys,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        max_year=max_year,
        output_prefix="automotive",
    )

    # =========================================================================
    # STEP 5: Run historic stock model
    # =========================================================================
    logging.info("[Plastics] Step 5: Running historic stock model")

    historic_eol_bc, historic_eol_auto = _run_historic_plastics_model(
        base_year=base_year,
        bc_sector=bc_sector,
        auto_sector=auto_sector,
        time_col=time_col,
        value_col=value_col,
    )

    # =========================================================================
    # STEP 4: Calculate total EOL flows
    # =========================================================================
    logging.info("[Plastics] Step 4: Calculating total EOL flows")

    total_future_eol = _calculate_total_eol(
        bu_eol_buildings=bu_eol_buildings,
        bu_eol_vehicles=bu_eol_vehicles,
        residual_bc_eol=residual_bc_eol,
        residual_auto_eol=residual_auto_eol,
        key_cols=key_cols,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
    )

    # =========================================================================
    # STEP 6: Calculate total future demand
    # =========================================================================
    logging.info("[Plastics] Step 6: Calculating total future demand")

    total_future_demand = _calculate_total_demand(
        bu_demand_buildings=bu_demand_buildings,
        bu_demand_vehicles=bu_demand_vehicles,
        residual_bc_future=residual_bc_future,
        residual_auto_future=residual_auto_future,
        start_pl=start_pl,
        growth_pl=growth_pl,
        bc_sector=bc_sector,
        auto_sector=auto_sector,
        key_cols=key_cols,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        max_year=max_year,
    )

    # =========================================================================
    # STEP 7: Run future model and combine
    # =========================================================================
    logging.info("[Plastics] Step 7: Running future model and combining")

    _run_future_plastics_model_and_combine(
        total_future_demand=total_future_demand,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
    )

    logging.info("=" * 60)
    logging.info("[Plastics] COUPLING COMPLETE!")
    logging.info("=" * 60)


def _map_buildings_to_plastics(
    flows: Optional[Dict],
    time_col: str,
    value_col: str,
    base_year: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Map buildings insulation flows to plastics dimensions."""
    empty_df = pd.DataFrame(
        columns=[time_col, "region", "sector", "polymer", "element", value_col]
    )

    if not flows:
        return empty_df, empty_df

    # Map demand
    df_ins = flows.get(SOURCE_FLOWS.buildings_insulation)
    if df_ins is not None:
        logging.info(
            f"[Plastics] Mapping buildings insulation demand: {len(df_ins)} rows"
        )
        mapped_demand = map_bottom_up_to_target(
            flow_df=df_ins.reset_index(),
            region_src_dim="Region",
            region_tgt_dim="region",
            regions_csv=MAPPING["buildings_plastics_regions"],
            products_csv=MAPPING["buildings_plastics_products"],
            target="plastics_fd_sv_gr",
        )
        mapped_demand = std_plastics_cols(mapped_demand)
        if "Time" in mapped_demand.columns and time_col not in mapped_demand.columns:
            mapped_demand = mapped_demand.rename(columns={"Time": time_col})
        bu_demand = mapped_demand
    else:
        bu_demand = empty_df

    # Map EOL
    df_ins_eol = flows.get(SOURCE_FLOWS.buildings_insulation_eol)
    if df_ins_eol is not None:
        logging.info(
            f"[Plastics] Mapping buildings insulation EOL: {len(df_ins_eol)} rows"
        )
        df_filtered = _filter_and_split_buildings_eol(
            df_ins_eol.reset_index(), base_year
        )
        if not df_filtered.empty:
            mapped_eol = map_bottom_up_to_target(
                flow_df=df_filtered,
                region_src_dim="Region",
                region_tgt_dim="region",
                regions_csv=MAPPING["buildings_plastics_regions"],
                products_csv=MAPPING["buildings_plastics_products"],
                target="plastics_fd_sv_gr",
            )
            mapped_eol = std_plastics_cols(mapped_eol)
            if "Time" in mapped_eol.columns and time_col not in mapped_eol.columns:
                mapped_eol = mapped_eol.rename(columns={"Time": time_col})
            bu_eol = mapped_eol
        else:
            bu_eol = empty_df
    else:
        bu_eol = empty_df

    return bu_demand, bu_eol


def _map_vehicles_to_plastics_flows(
    flows: Optional[Dict],
    time_col: str,
    value_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Map vehicles plastics flows to plastics dimensions."""
    empty_df = pd.DataFrame(
        columns=[time_col, "region", "sector", "polymer", "element", value_col]
    )

    if not flows:
        return empty_df, empty_df

    # Map demand
    df_veh = flows.get(SOURCE_FLOWS.vehicles_plastics)
    if df_veh is not None:
        logging.info(f"[Plastics] Mapping vehicles plastics demand: {len(df_veh)} rows")
        mapped_demand = map_vehicles_to_plastics(
            flow_df=df_veh.reset_index(),
            regions_csv=MAPPING["vehicles_plastics_regions"],
            products_csv=MAPPING["vehicles_plastics_products"],
        )
        mapped_demand = std_plastics_cols(mapped_demand)
        if "Time" in mapped_demand.columns and time_col not in mapped_demand.columns:
            mapped_demand = mapped_demand.rename(columns={"Time": time_col})
        bu_demand = mapped_demand
    else:
        bu_demand = empty_df

    # Map EOL (no cohort filtering needed for vehicles)
    df_veh_eol = flows.get(SOURCE_FLOWS.vehicles_plastics_eol)
    if df_veh_eol is not None:
        logging.info(
            f"[Plastics] Mapping vehicles plastics EOL: {len(df_veh_eol)} rows"
        )
        mapped_eol = map_vehicles_to_plastics(
            flow_df=df_veh_eol.reset_index(),
            regions_csv=MAPPING["vehicles_plastics_regions"],
            products_csv=MAPPING["vehicles_plastics_products"],
        )
        mapped_eol = std_plastics_cols(mapped_eol)
        if "Time" in mapped_eol.columns and time_col not in mapped_eol.columns:
            mapped_eol = mapped_eol.rename(columns={"Time": time_col})
        bu_eol = mapped_eol
    else:
        bu_eol = empty_df

    return bu_demand, bu_eol


def _save_plastics_intermediate_files(
    bu_demand_buildings: pd.DataFrame,
    bu_eol_buildings: pd.DataFrame,
    bu_demand_vehicles: pd.DataFrame,
    bu_eol_vehicles: pd.DataFrame,
    time_col: str,
    value_col: str,
) -> None:
    """Save intermediate plastics mapping files."""
    base_dir = TOPDOWN["plastics_fd_sv_gr_dir"]

    files = {
        "bottom_up_demand_buildings.csv": bu_demand_buildings,
        "bottom_up_eol_buildings.csv": bu_eol_buildings,
        "bottom_up_demand_vehicles.csv": bu_demand_vehicles,
        "bottom_up_eol_vehicles.csv": bu_eol_vehicles,
    }

    for filename, df in files.items():
        path = os.path.join(base_dir, filename)
        ensure_dir(path)
        df.to_csv(path, index=False)
        logging.info(f"[Plastics] Saved: {filename}")


def _calculate_sector_residual(
    sector_name: str,
    bu_demand: pd.DataFrame,
    start_values: pd.DataFrame,
    growth_rates: pd.DataFrame,
    lifetime_df: pd.DataFrame,
    merge_keys: List[str],
    time_col: str,
    value_col: str,
    base_year: int,
    max_year: int,
    output_prefix: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate residual demand and EOL for a single sector.

    Returns (residual_future, residual_eol)
    """
    # Filter to sector
    start_sector = start_values[start_values["sector"] == sector_name].copy()
    growth_sector = growth_rates[growth_rates["sector"] == sector_name].copy()

    logging.info(f"[Plastics] {sector_name}: {len(start_sector)} start value rows")

    # Aggregate bottom-up at base year
    bu_base = bu_demand[bu_demand[time_col] == base_year].copy()
    bu_base_agg = bu_base.groupby(merge_keys, as_index=False)[value_col].sum()

    logging.info(
        f"[Plastics] {sector_name} bottom-up at base year: {bu_base_agg[value_col].sum():.2f}"
    )

    # Calculate residual: start_value - bottom_up
    residual_base = start_sector.merge(
        bu_base_agg[merge_keys + [value_col]].rename(columns={value_col: "bu_val"}),
        on=merge_keys,
        how="left",
    )
    residual_base["bu_val"] = residual_base["bu_val"].fillna(0)
    residual_base["residual"] = (
        residual_base[value_col] - residual_base["bu_val"]
    ).clip(lower=0)
    residual_base = residual_base[merge_keys + ["residual"]].rename(
        columns={"residual": value_col}
    )

    logging.info(
        f"[Plastics] {sector_name} residual at base year: {residual_base[value_col].sum():.2f}"
    )

    # Project residual with cumulative growth
    residual_future = fc.compute_residual_cumulative_growth(
        residual_base_df=residual_base,
        growth_rate_df=growth_sector,
        base_year=base_year,
        max_year=max_year,
        key_cols=tuple(merge_keys),
        time_col=time_col,
        value_col=value_col,
    )

    # Save residual
    residual_path = os.path.join(
        TOPDOWN["plastics_fd_sv_gr_dir"], f"residual_demand_{output_prefix}.csv"
    )
    residual_future.to_csv(residual_path, index=False)
    logging.info(f"[Plastics] {sector_name} residual saved: {residual_path}")

    # Calculate residual EOL
    residual_eol = compute_residual_eol_inline(
        residual_demand_df=residual_future,
        lifetime_df=lifetime_df,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        max_year=max_year,
    )

    # Save residual EOL
    residual_eol_path = os.path.join(
        TOPDOWN["plastics_fd_sv_gr_dir"], f"residual_eol_{output_prefix}.csv"
    )
    residual_eol.to_csv(residual_eol_path, index=False)
    logging.info(f"[Plastics] {sector_name} residual EOL: {len(residual_eol)} rows")

    return residual_future, residual_eol


def _run_historic_plastics_model(
    base_year: int,
    bc_sector: str,
    auto_sector: str,
    time_col: str,
    value_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run historic plastics model and extract continuing EOL.

    Returns (historic_eol_bc, historic_eol_auto)
    """
    empty_df = pd.DataFrame(
        columns=[
            time_col,
            "age-cohort",
            "region",
            "sector",
            "polymer",
            "element",
            value_col,
        ]
    )

    try:
        from src.plastics.plastics_model import PlasticsModel
        from src.common.common_cfg import GeneralCfg

        # Load and modify config
        with open("config/plastics_baseline.yml", "r") as f:
            config_dict = yaml.safe_load(f)

        config_dict["do_export"] = {"pickle": False, "csv": False}
        config_dict["visualization"] = {
            "inflow": {"do_visualize": False},
            "production": {"do_visualize": False},
            "outflow": {"do_visualize": False},
            "sankey": {"do_visualize": False},
            "dashboard": {"do_visualize": False},
        }

        cfg = GeneralCfg.from_model_class(**config_dict)
        model = PlasticsModel(cfg=cfg)

        # Zero parameters for future years
        time_items = list(model.mfa.dims["t"].items)
        _zero_future_parameters(model, time_items, base_year)

        # Run computation
        model.mfa.compute()
        logging.info("[Plastics] Historic model computation completed")

        # Export flows
        _export_historic_plastics_flows(model)

        # Extract continuing EOL for both sectors
        historic_eol_bc = extract_eol_flow_memory_efficient(
            mfa_model=model,
            flow_name="End use stock => Waste collection",
            base_year=base_year,
            sector_filter=bc_sector,
        )

        historic_eol_auto = extract_eol_flow_memory_efficient(
            mfa_model=model,
            flow_name="End use stock => Waste collection",
            base_year=base_year,
            sector_filter=auto_sector,
        )

        # Save EOL files
        if not historic_eol_bc.empty:
            path = os.path.join(
                TOPDOWN["plastics_fd_sv_gr_dir"], "historic_continuing_eol_bc.csv"
            )
            historic_eol_bc.to_csv(path, index=False)
            logging.info(f"[Plastics] Historic EOL (B&C): {len(historic_eol_bc)} rows")

        if not historic_eol_auto.empty:
            path = os.path.join(
                TOPDOWN["plastics_fd_sv_gr_dir"],
                "historic_continuing_eol_automotive.csv",
            )
            historic_eol_auto.to_csv(path, index=False)
            logging.info(
                f"[Plastics] Historic EOL (Automotive): {len(historic_eol_auto)} rows"
            )

        return historic_eol_bc, historic_eol_auto

    except Exception as e:
        logging.error(f"[Plastics] Failed to run historic model: {e}")
        import traceback

        traceback.print_exc()
        return empty_df, empty_df


def _zero_future_parameters(model, time_items: List, base_year: int) -> None:
    """Zero out parameters for years >= base_year in historic model."""
    # Zero DomesticDemand
    demand_param = model.mfa.parameters["DomesticDemand"]
    zeroed_years = 0
    for t_idx, year in enumerate(time_items):
        if year >= base_year:
            demand_param.values[:, t_idx, :, :, :] = 0.0
            zeroed_years += 1
    logging.info(f"[Plastics] Zeroed DomesticDemand for {zeroed_years} years")

    # Zero import/export parameters
    for pname in ["ImportNew", "ExportNew", "ImportRateNew", "ExportRateNew"]:
        if pname not in model.mfa.parameters:
            continue
        param = model.mfa.parameters[pname]
        arr = param.values
        nd = arr.ndim
        time_axis = 2 if nd >= 3 else 1

        for t_idx, year in enumerate(time_items):
            if year >= base_year:
                indexer = [slice(None)] * nd
                indexer[time_axis] = t_idx
                arr[tuple(indexer)] = 0.0


def _export_historic_plastics_flows(model) -> None:
    """Export historic plastics flows with cohort aggregation."""
    output_dir = "data/baseline_plastics/output/export/flows"
    os.makedirs(output_dir, exist_ok=True)

    export_flows = [
        "sysenv => Polymer market",
        "Polymer market => PRIMARY Plastics manufacturing",
        "Polymer market => SECONDARY Plastics manufacturing",
        "Plastics manufacturing => Plastics market",
        "Plastics market => End use stock",
        "End use stock => Waste collection",
        "Waste collection => Waste sorting",
        "Waste sorting => Sorted waste market",
        "Sorted waste market => Recycling",
        "Recycling => RECYCLATE sysenv",
        "Recycling => LOSSES sysenv",
    ]

    exported = 0
    for flow_name in export_flows:
        if flow_name not in model.mfa.flows:
            continue

        flow = model.mfa.flows[flow_name]
        has_cohort = "c" in flow.dims.letters

        try:
            if has_cohort:
                flow_agg = flow.sum_over(("c",))
                df = flow_agg.to_df().reset_index()
            else:
                df = flow.to_df().reset_index()

            safe_name = flow_name.replace(" => ", "__").replace(" ", "_").lower()
            out_path = os.path.join(output_dir, f"{safe_name}_baseline.csv")
            fc.export_numeric_csv(df, out_path, value_cols=("value",))
            exported += 1
        except Exception as e:
            logging.error(f"[Plastics] Failed to export '{flow_name}': {e}")

    logging.info(f"[Plastics] Historic: exported {exported} flows")


def _calculate_total_eol(
    bu_eol_buildings: pd.DataFrame,
    bu_eol_vehicles: pd.DataFrame,
    residual_bc_eol: pd.DataFrame,
    residual_auto_eol: pd.DataFrame,
    key_cols: Tuple[str, ...],
    time_col: str,
    value_col: str,
    base_year: int,
) -> pd.DataFrame:
    """Calculate total future EOL from all components."""
    # Aggregate each component (remove cohort)
    bu_eol_buildings_agg = aggregate_eol_no_cohort(bu_eol_buildings, value_col)
    bu_eol_vehicles_agg = aggregate_eol_no_cohort(bu_eol_vehicles, value_col)
    residual_bc_eol_agg = aggregate_eol_no_cohort(residual_bc_eol, value_col)
    residual_auto_eol_agg = aggregate_eol_no_cohort(residual_auto_eol, value_col)

    # Save aggregated files
    base_dir = TOPDOWN["plastics_fd_sv_gr_dir"]
    bu_eol_buildings_agg.to_csv(
        os.path.join(base_dir, "bottom_up_eol_buildings_aggregated.csv"), index=False
    )
    bu_eol_vehicles_agg.to_csv(
        os.path.join(base_dir, "bottom_up_eol_vehicles_aggregated.csv"), index=False
    )
    residual_bc_eol_agg.to_csv(
        os.path.join(base_dir, "residual_eol_bc_aggregated.csv"), index=False
    )
    residual_auto_eol_agg.to_csv(
        os.path.join(base_dir, "residual_eol_automotive_aggregated.csv"), index=False
    )

    # Calculate total
    total_future_eol = fc.compute_total_future_flodym(
        key_cols=key_cols,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        include_base_year=True,
        flows={
            "buildings_eol": bu_eol_buildings_agg,
            "vehicles_eol": bu_eol_vehicles_agg,
            "residual_bc_eol": residual_bc_eol_agg,
            "residual_auto_eol": residual_auto_eol_agg,
        },
    )

    # Save total
    tfe_path = os.path.join(base_dir, "total_future_eol_flows.csv")
    total_future_eol.to_csv(tfe_path, index=False)
    logging.info(f"[Plastics] Total future EOL: {len(total_future_eol)} rows")

    return total_future_eol


def _calculate_total_demand(
    bu_demand_buildings: pd.DataFrame,
    bu_demand_vehicles: pd.DataFrame,
    residual_bc_future: pd.DataFrame,
    residual_auto_future: pd.DataFrame,
    start_pl: pd.DataFrame,
    growth_pl: pd.DataFrame,
    bc_sector: str,
    auto_sector: str,
    key_cols: Tuple[str, ...],
    time_col: str,
    value_col: str,
    base_year: int,
    max_year: int,
) -> pd.DataFrame:
    """Calculate total future demand for all sectors."""

    # B&C sector: buildings + residual
    bu_demand_future_bc = bu_demand_buildings[
        bu_demand_buildings[time_col] >= base_year
    ].copy()
    bc_total = fc.compute_total_future_flodym(
        key_cols=key_cols,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        include_base_year=True,
        flows={"buildings": bu_demand_future_bc, "residual": residual_bc_future},
    )
    logging.info(f"[Plastics] B&C demand: {len(bc_total)} rows")

    # Automotive sector: vehicles + residual
    bu_demand_future_auto = bu_demand_vehicles[
        bu_demand_vehicles[time_col] >= base_year
    ].copy()
    auto_total = fc.compute_total_future_flodym(
        key_cols=key_cols,
        time_col=time_col,
        value_col=value_col,
        base_year=base_year,
        include_base_year=True,
        flows={"vehicles": bu_demand_future_auto, "residual": residual_auto_future},
    )
    logging.info(f"[Plastics] Automotive demand: {len(auto_total)} rows")

    # Other sectors: project from start_value
    start_other = start_pl[
        (start_pl["sector"] != bc_sector) & (start_pl["sector"] != auto_sector)
    ].copy()
    growth_other = growth_pl[
        (growth_pl["sector"] != bc_sector) & (growth_pl["sector"] != auto_sector)
    ].copy()

    if not start_other.empty and not growth_other.empty:
        other_total = fc.compute_residual_cumulative_growth(
            residual_base_df=start_other,
            growth_rate_df=growth_other,
            base_year=base_year,
            max_year=max_year,
            key_cols=key_cols,
            time_col=time_col,
            value_col=value_col,
        )
        logging.info(f"[Plastics] Other sectors demand: {len(other_total)} rows")
    else:
        other_total = pd.DataFrame(columns=list(key_cols) + [time_col, value_col])

    # Combine all sectors
    total_future_demand = pd.concat(
        [bc_total, auto_total, other_total], ignore_index=True
    )
    total_future_demand = total_future_demand.groupby(
        list(key_cols) + [time_col], as_index=False
    )[value_col].sum()

    # Save
    tfd_path = os.path.join(TOPDOWN["plastics_fd_sv_gr_dir"], "total_future_demand.csv")
    ensure_dir(tfd_path)
    total_future_demand.to_csv(tfd_path, index=False)
    logging.info(f"[Plastics] Total future demand: {len(total_future_demand)} rows")
    logging.info(
        f"[Plastics] Sectors: {sorted(total_future_demand['sector'].unique())}"
    )

    return total_future_demand


def _run_future_plastics_model_and_combine(
    total_future_demand: pd.DataFrame,
    time_col: str,
    value_col: str,
    base_year: int,
) -> None:
    """Run future plastics model and combine with historic outputs."""

    # Save as FinalDemand.csv
    final_demand_path = os.path.join(
        TOPDOWN["plastics_fd_sv_gr_dir"], "FinalDemand.csv"
    )
    final_demand_cols = ["region", "time", "sector", "polymer", "element", "value"]

    export_df = total_future_demand.copy()
    for col in final_demand_cols:
        if col not in export_df.columns:
            if col == "element":
                export_df[col] = "All"
            elif col == "time":
                export_df[col] = export_df.get(time_col, base_year)
            else:
                export_df[col] = "Unknown"

    if time_col != "time" and time_col in export_df.columns:
        export_df = export_df.rename(columns={time_col: "time"})
    if value_col != "value" and value_col in export_df.columns:
        export_df = export_df.rename(columns={value_col: "value"})

    export_df = export_df[[c for c in final_demand_cols if c in export_df.columns]]
    export_df.to_csv(final_demand_path, index=False)
    logging.info(f"[Plastics] FinalDemand.csv saved: {final_demand_path}")

    # Run future model
    try:
        from src.plastics.plastics_model import PlasticsModel
        from src.common.common_cfg import GeneralCfg

        with open("config/plastics_combined_future.yml", "r") as f:
            config_dict = yaml.safe_load(f)

        config_dict["do_export"] = {"pickle": False, "csv": False}
        config_dict["visualization"] = {
            "inflow": {"do_visualize": False},
            "production": {"do_visualize": False},
            "outflow": {"do_visualize": False},
            "sankey": {"do_visualize": False},
            "dashboard": {"do_visualize": False},
        }

        cfg = GeneralCfg.from_model_class(**config_dict)
        model = PlasticsModel(cfg=cfg)
        model.mfa.compute()
        logging.info("[Plastics] Future model computation completed")

        # Export flows
        _export_future_plastics_flows(model)

    except Exception as e:
        logging.error(f"[Plastics] Future model failed: {e}")
        return

    # Combine historic + future
    _combine_plastics_flows(base_year)


def _export_future_plastics_flows(model) -> None:
    """Export future plastics flows."""
    output_dir = "data/combined_plastics_future/output/export/flows"
    os.makedirs(output_dir, exist_ok=True)

    export_flows = [
        "sysenv => Polymer market",
        "Polymer market => PRIMARY Plastics manufacturing",
        "Polymer market => SECONDARY Plastics manufacturing",
        "Plastics manufacturing => Plastics market",
        "Plastics market => End use stock",
        "End use stock => Waste collection",
        "Waste collection => Waste sorting",
        "Waste sorting => Sorted waste market",
        "Sorted waste market => Recycling",
        "Recycling => RECYCLATE sysenv",
        "Recycling => LOSSES sysenv",
    ]

    exported = 0
    for flow_name in export_flows:
        if flow_name not in model.mfa.flows:
            continue

        flow = model.mfa.flows[flow_name]
        has_cohort = "c" in flow.dims.letters

        try:
            if has_cohort:
                flow_agg = flow.sum_over(("c",))
                df = flow_agg.to_df().reset_index()
            else:
                df = flow.to_df().reset_index()

            safe_name = flow_name.replace(" => ", "__").replace(" ", "_").lower()
            out_path = os.path.join(output_dir, f"{safe_name}_combined_future.csv")
            fc.export_numeric_csv(df, out_path, value_cols=("value",))
            exported += 1
        except Exception as e:
            logging.error(f"[Plastics] Failed to export '{flow_name}': {e}")

    logging.info(f"[Plastics] Future: exported {exported} flows")


def _combine_plastics_flows(base_year: int) -> None:
    """Combine historic and future plastics flow CSVs."""
    historic_dir = "data/baseline_plastics/output/export/flows"
    future_dir = "data/combined_plastics_future/output/export/flows"
    combined_dir = "data/combined_plastics/output/flows"

    os.makedirs(combined_dir, exist_ok=True)

    if not os.path.exists(historic_dir) or not os.path.exists(future_dir):
        logging.warning("[Plastics] Historic or future directory not found")
        return

    historic_files = glob.glob(os.path.join(historic_dir, "*.csv"))
    future_files = glob.glob(os.path.join(future_dir, "*.csv"))

    logging.info(
        f"[Plastics] Found {len(historic_files)} historic, {len(future_files)} future files"
    )

    def normalize_filename(fname):
        base = fname.replace(".csv", "")
        for suffix in ("_baseline", "_combined_future", "_historic", "_future"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return base

    # Build pairs
    flow_pairs = {}
    for fpath in historic_files:
        key = normalize_filename(os.path.basename(fpath))
        flow_pairs.setdefault(key, {})["historic"] = fpath

    for fpath in future_files:
        key = normalize_filename(os.path.basename(fpath))
        flow_pairs.setdefault(key, {})["future"] = fpath

    # Combine pairs
    combined_count = 0
    for flow_key, paths in flow_pairs.items():
        if "historic" in paths and "future" in paths:
            out_path = os.path.join(combined_dir, f"{flow_key}_combined.csv")
            try:
                fc.combine_hist_future_flodym(
                    historic_path=paths["historic"],
                    future_path=paths["future"],
                    output_path=out_path,
                    time_col="time",
                    value_col="value",
                    base_year=base_year,
                )
                combined_count += 1
            except Exception as e:
                logging.warning(f"[Plastics] Failed to combine {flow_key}: {e}")

    logging.info(f"[Plastics] Combined {combined_count} flow files")


# =============================================================================

# MAIN ENTRY POINT

# =============================================================================


def main():
    """Main entry point for the combined model."""
    try:
        flows_buildings: Optional[Dict[str, pd.DataFrame]] = None
        flows_vehicles: Optional[Dict[str, pd.DataFrame]] = None

        # ---------------------------------------------------------------------
        # Step 1: Run bottom-up models
        # ---------------------------------------------------------------------
        if not DOWNSTREAM_ONLY:
            if USE_BUILDINGS:
                logging.info("Running buildings model...")
                flows_buildings = run_eumfa("config/buildings.yml")

            if USE_VEHICLES:
                try:
                    logging.info("Running vehicles model...")
                    flows_vehicles = run_eumfa("config/vehicles.yml")
                except Exception as e:
                    logging.warning(f"Vehicles model failed: {e}")

        # ---------------------------------------------------------------------
        # Step 2: Run material couplings
        # ---------------------------------------------------------------------
        if COMBINE_CEMENT:
            run_cement_coupling(flows_buildings)

        if COMBINE_PLASTICS:
            run_plastics_coupling(flows_buildings, flows_vehicles)

        logging.info("=" * 60)
        logging.info("COMBINED MODEL COMPLETE")
        logging.info("=" * 60)

    except Exception as e:
        logging.exception(f"Combined model failed: {e}")
        raise


if __name__ == "__main__":
    main()
