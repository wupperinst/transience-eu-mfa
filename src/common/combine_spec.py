
# src/common/combine_spec.py

from dataclasses import dataclass
from typing import Optional, Dict, Tuple

MAPPING = {
    "buildings_plastics_regions": "data/baseline_combined/mapping_buildings_plastics_regions.csv",
    "buildings_plastics_products": "data/baseline_combined/mapping_buildings_plastics_products.csv",
    "vehicles_plastics_regions": "data/baseline_combined/mapping_vehicles_plastics_regions.csv",
    "vehicles_plastics_products": "data/baseline_combined/mapping_vehicles_plastics_products.csv",

    "buildings_concrete_regions": "data/baseline_combined/mapping_buildings_concrete_regions.csv",
    "buildings_concrete_products": "data/baseline_combined/mapping_buildings_concrete_products.csv",  # semicolon

    "vehicles_steel_regions": "data/baseline_combined/mapping_vehicles_steel_regions.csv",
    "vehicles_steel_products": "data/baseline_combined/mapping_vehicles_steel_products.csv",

    "buildings_steel_regions": "data/baseline_combined/mapping_buildings_steel_regions.csv",
    "buildings_steel_products": "data/baseline_combined/mapping_buildings_steel_products.csv",
}

TOPDOWN = {
    "plastics_dir": "data/baseline_plastics_flows/input/datasets",
    "steel_dir": "data/baseline_steel_flows/input/datasets",


    "cement_stock_dir": "data/baseline_cement_stock_flows/input/datasets",

    "cement_flows_dir": "data/baseline_cement_stock_flows/input/datasets",

    "plastics_start": "data/baseline_plastics_flows/input/datasets/start_value.csv",
    "plastics_growth": "data/baseline_plastics_flows/input/datasets/growth_rate.csv",

    "steel_start": "data/baseline_steel_flows/input/datasets/start_value.csv",
    "steel_growth": "data/baseline_steel_flows/input/datasets/growth_rate.csv",

    "cement_start": "data/baseline_cement_stock_flows/input/datasets/start_value.csv",
    "cement_growth": "data/baseline_cement_stock_flows/input/datasets/growth_rate.csv",
}

DIM_CATALOGS: Dict[str, Dict[str, Tuple[str, Optional[str]]]] = {
    "plastics": {
        "sector": ("data/baseline_plastics_flows/input/dimensions/end_use_sectors_all.csv", None),
        "polymer": ("data/baseline_plastics_flows/input/dimensions/polymers.csv", None),
        "element": ("data/baseline_plastics_flows/input/dimensions/elements.csv", None),
    },
    "steel": {
        "sector": ("data/baseline_steel_flows/input/dimensions/end_use_sectors.csv", None),
        "product": ("data/baseline_steel_flows/input/dimensions/products.csv", None),
        "intermediate": ("data/baseline_steel_flows/input/dimensions/intermediates.csv", None),
        "element": ("data/baseline_steel_flows/input/dimensions/elements.csv", None),
    },
    "cement": {
        "Concrete product simple": ("data/baseline_cement_stock_flows/input/dimensions/concrete_products_simple.csv", None),
        "End use sector": ("data/baseline_cement_stock_flows/input/dimensions/end_use_sectors.csv", None),
    },
}

@dataclass
class SourceFlowNames:
    buildings_steel: str = "sysenv => Steel stock in buildings"
    buildings_concrete: str = "sysenv => Concrete stock in buildings"
    buildings_insulation: str = "sysenv => Insulation stock in buildings"

    vehicles_steel: str = "sysenv => Steel stock in vehicles"
    vehicles_plastics: str = "sysenv => Plastics stock in vehicles"

SOURCE_FLOWS = SourceFlowNames()

def get_dim_catalog(target: str) -> Dict[str, Tuple[str, Optional[str]]]:
    return DIM_CATALOGS[target]

def products_csv_sep_for(target: str) -> Optional[str]:
    return None