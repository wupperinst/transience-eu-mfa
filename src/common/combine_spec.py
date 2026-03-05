# src/common/combine_spec.py

"""
Configuration and constants for the EU MFA Combined Model.

This module defines:
- File paths for mapping files and top-down model inputs
- Dimension catalogs for target materials
- Constants for plastics model configuration
- Source flow name definitions

"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# =============================================================================

# FILE PATHS

# =============================================================================

# --- Mapping Files ---

# Maps bottom-up model dimensions to top-down model dimensions

MAPPING = {
    # Buildings -> Plastics (insulation)
    "buildings_plastics_regions": "data/baseline_combined/mapping_buildings_plastics_regions.csv",
    "buildings_plastics_products": "data/baseline_combined/mapping_buildings_plastics_products.csv",
    # Vehicles -> Plastics
    "vehicles_plastics_regions": "data/baseline_combined/mapping_vehicles_plastics_regions.csv",
    "vehicles_plastics_products": "data/baseline_combined/mapping_vehicles_plastics_products.csv",
    # Buildings -> Cement (concrete)
    "buildings_concrete_regions": "data/baseline_combined/mapping_buildings_concrete_regions.csv",
    "buildings_concrete_products": "data/baseline_combined/mapping_buildings_concrete_products.csv",
    # Buildings -> Steel
    "buildings_steel_regions": "data/baseline_combined/mapping_buildings_steel_regions.csv",
    "buildings_steel_products": "data/baseline_combined/mapping_buildings_steel_products.csv",
    # Vehicles -> Steel
    "vehicles_steel_regions": "data/baseline_combined/mapping_vehicles_steel_regions.csv",
    "vehicles_steel_products": "data/baseline_combined/mapping_vehicles_steel_products.csv",
}

# --- Top-Down Model Paths ---

TOPDOWN = {
    # Legacy paths (for steel/cement flows models)
    "plastics_dir": "data/baseline_plastics_flows/input/datasets",
    "steel_dir": "data/baseline_steel_flows/input/datasets",
    "cement_stock_dir": "data/baseline_cement_stock_flows/input/datasets",
    "cement_flows_dir": "data/baseline_cement_stock_flows/input/datasets",
    # Start value and growth rate files
    "plastics_start": "data/baseline_plastics_flows/input/datasets/start_value.csv",
    "plastics_growth": "data/baseline_plastics_flows/input/datasets/growth_rate.csv",
    "steel_start": "data/baseline_steel_flows/input/datasets/start_value.csv",
    "steel_growth": "data/baseline_steel_flows/input/datasets/growth_rate.csv",
    "cement_start": "data/baseline_cement_stock_flows/input/datasets/start_value.csv",
    "cement_growth": "data/baseline_cement_stock_flows/input/datasets/growth_rate.csv",
    # Plastics baseline model (production-driven, for historic stock)
    "plastics_baseline_dir": "data/baseline_plastics/input/datasets",
    "plastics_baseline_lifetime": "data/baseline_plastics/input/datasets/Lifetime.csv",
    "plastics_baseline_domestic_demand": "data/baseline_plastics/input/datasets/DomesticDemand.csv",
    # Plastics fd-sv-gr model (final-demand-driven with start value & growth rate)
    "plastics_fd_sv_gr_dir": "data/fd-sv-gr_plastics/input/datasets",
    "plastics_fd_sv_gr_start": "data/fd-sv-gr_plastics/input/datasets/start_value.csv",
    "plastics_fd_sv_gr_growth": "data/fd-sv-gr_plastics/input/datasets/growth_rate.csv",
    # Combined output
    "plastics_combined_output_dir": "data/combined_plastics/output",
}


# =============================================================================

# DIMENSION CATALOGS

# =============================================================================

# Maps dimension names to (csv_path, separator) for each target material.

# Used for expanding "all" values in mapping files.

DIM_CATALOGS: Dict[str, Dict[str, Tuple[str, Optional[str]]]] = {
    "plastics": {
        "sector": (
            "data/baseline_plastics_flows/input/dimensions/end_use_sectors_all.csv",
            None,
        ),
        "polymer": ("data/baseline_plastics_flows/input/dimensions/polymers.csv", None),
        "element": ("data/baseline_plastics_flows/input/dimensions/elements.csv", None),
    },
    "plastics_fd_sv_gr": {
        "sector": (
            "data/fd-sv-gr_plastics/input/dimensions/end_use_sectors_MainSectors.csv",
            None,
        ),
        "polymer": ("data/fd-sv-gr_plastics/input/dimensions/polymers.csv", None),
        "element": ("data/fd-sv-gr_plastics/input/dimensions/elements.csv", None),
    },
    "steel": {
        "sector": (
            "data/baseline_steel_flows/input/dimensions/end_use_sectors.csv",
            None,
        ),
        "product": ("data/baseline_steel_flows/input/dimensions/products.csv", None),
        "intermediate": (
            "data/baseline_steel_flows/input/dimensions/intermediates.csv",
            None,
        ),
        "element": ("data/baseline_steel_flows/input/dimensions/elements.csv", None),
    },
    "cement": {
        "Concrete product simple": (
            "data/baseline_cement_stock_flows/input/dimensions/concrete_products_simple.csv",
            None,
        ),
        "End use sector": (
            "data/baseline_cement_stock_flows/input/dimensions/end_use_sectors.csv",
            None,
        ),
    },
}


# =============================================================================

# PLASTICS MODEL CONSTANTS

# =============================================================================

PLASTICS_KEY_COLS = ("region", "sector", "polymer", "element")
PLASTICS_TIME_COL = "time"
PLASTICS_VALUE_COL = "value"
PLASTICS_BASE_YEAR = 2023
PLASTICS_MAX_YEAR = 2050

# Sector names in plastics model

PLASTICS_BC_SECTOR = "Building and Construction"
PLASTICS_AUTO_SECTOR = "Automotive"

# Polymers used for building insulation (from mapping file)

PLASTICS_INSULATION_POLYMERS = ["PS-E", "PUR"]


# =============================================================================

# SOURCE FLOW NAMES

# =============================================================================


@dataclass
class SourceFlowNames:
    """Flow names from bottom-up models used for coupling."""

    # Buildings inflows (demand)
    buildings_steel: str = "sysenv => Steel stock in buildings"
    buildings_concrete: str = "sysenv => Concrete stock in buildings"
    buildings_insulation: str = "sysenv => Insulation stock in buildings"

    # Buildings outflows (EOL)
    buildings_steel_eol: str = "Steel stock in buildings => sysenv"
    buildings_concrete_eol: str = "Concrete stock in buildings => sysenv"
    buildings_insulation_eol: str = "Insulation stock in buildings => sysenv"

    # Vehicles inflows (demand)
    vehicles_steel: str = "sysenv => Steel stock in vehicles"
    vehicles_plastics: str = "sysenv => Plastics stock in vehicles"

    # Vehicles outflows (EOL)
    vehicles_plastics_eol: str = "Plastics stock in vehicles => sysenv"


SOURCE_FLOWS = SourceFlowNames()


# =============================================================================

# HELPER FUNCTIONS

# =============================================================================


def get_dim_catalog(target: str) -> Dict[str, Tuple[str, Optional[str]]]:
    """Return dimension catalog for a given target material."""
    if target not in DIM_CATALOGS:
        raise ValueError(
            f"Unknown target '{target}'. Available: {list(DIM_CATALOGS.keys())}"
        )
    return DIM_CATALOGS[target]


def get_plastics_config() -> Dict:
    """Return plastics-specific configuration for combined model."""
    return {
        "key_cols": PLASTICS_KEY_COLS,
        "time_col": PLASTICS_TIME_COL,
        "value_col": PLASTICS_VALUE_COL,
        "base_year": PLASTICS_BASE_YEAR,
        "max_year": PLASTICS_MAX_YEAR,
        "bc_sector": PLASTICS_BC_SECTOR,
        "auto_sector": PLASTICS_AUTO_SECTOR,
        "insulation_polymers": PLASTICS_INSULATION_POLYMERS,
    }
