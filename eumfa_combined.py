# 1. run bottom up model, extract material demand and eol flows
# 2. map dimensions
# 3. read top down demand, optionally map, calculate residual demand (top down - bottom up) and project residual demand
# 4. run stock model with residual demand to calculate residual eol flows
# 5. calculate total material demand and total eol flow
# 6. run with these inputs flow model
# 7. combine historic and future tables

import logging
import os
import sys
import glob
import csv
import gc
from dataclasses import dataclass
from typing import Dict, List, Iterable, Optional

import pandas as pd

from run_eumfa import run_eumfa
from src.common.combine_flows import FlowCalculator

"""Auswahl (beibehaltbar für Nutzer)"""
# Diese beiden Listen bleiben konfigurierbar wie angefragt
bottom_up_sectors_to_consider = ["buildings"]
materials_to_consider = ["concrete"]

# Optionaler Modus nur Downstream rechnen (nutzt bereits vorbereitete Inputs)
downstream_only = False
baseyear = 2023

# Mapping-Dateien (später erweiterbar)
MAPPING_FILES = {
    ("buildings", "concrete"): "data/baseline_combined/mapping_buildings_concrete.csv",
    # ("buildings", "plastics"): "data/baseline_combined/mapping_buildings_plastics.csv",
    # ("buildings", "steel"): "data/baseline_combined/mapping_buildings_steel.csv",
    # ("vehicles", "plastics"): "data/baseline_combined/mapping_vehicles_plastics.csv",
    # ("vehicles", "steel"): "data/baseline_combined/mapping_vehicles_steel.csv",
}

# Logging schlanker halten (WARN standard), bei Bedarf INFO setzen
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
# Datenklassen & Orchestrator
#------------------------------------------------------------------------------

@dataclass(frozen=True)
class MaterialConfig:
    material: str
    sector: str
    mapping_file: str
    relevant_flows: List[str]
    bottom_up_to_stock_flow: str
    stock_to_eol_flow: str
    tag: str
    # Generalisierte Parameter
    product_column: str
    default_sector: str = "Buildings"
    default_region: str = "EU28"
    start_value_file: str = ""
    growth_rate_file: str = ""
    demand_future_file: str = ""
    stock_model_config: str = ""
    flows_model_config: str = ""
    market_future_file: str = ""          # Aus Stock-Modell (top-down residueller Anteil)
    eol_future_file: str = ""             # Aus Stock-Modell resultierende EOL Flüsse
    total_future_demand_file: str = ""     # Aggregierte Gesamt-Nachfrage (Bottom-up + Residual)
    total_future_eol_file: str = ""        # Aggregierte Gesamt-EOL Flüsse
    flow_results_folder: str = ""          # Ordner mit historic/future Flow Exporten

class EUMFAOrchestrator:
    def __init__(
        self,
        base_year: int,
        flow_calculator: Optional[FlowCalculator] = None,
        bottom_up_output_dir: str = "data/baseline/output",
        cement_stock_dir: str = "data/baseline_cement_stock_flows",
    ):
        self.base_year = base_year
        self.flow_calc = flow_calculator or FlowCalculator()
        self.bottom_up_output_dir = bottom_up_output_dir
        self.cement_stock_dir = cement_stock_dir

    # ---------------- Bottom-Up -----------------
    def run_bottom_up_models(self, configs: Iterable[str]) -> Dict[str, pd.DataFrame]:
        flows: Dict[str, pd.DataFrame] = {}
        for cfg in configs:
            logger.info("Starte Bottom-Up Modell: %s", cfg)
            model_flows = run_eumfa(cfg)
            flows.update(model_flows)
        return flows

    # ---------------- Mapping --------------------
    def _load_mapping(self, mapping_file: str) -> List[Dict[str, str]]:
        with open(mapping_file, mode="r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    def map_and_store_flows(self, flows: Dict[str, pd.DataFrame], cfg: MaterialConfig) -> Dict[str, pd.DataFrame]:
        mapping = self._load_mapping(cfg.mapping_file)
        mapped: Dict[str, pd.DataFrame] = {}
        for flow_name, df in flows.items():
            if flow_name not in cfg.relevant_flows:
                continue
            logger.info("Mappe Flow: %s", flow_name)
            remapped = self.flow_calc.map_dimensions(df, mapping)
            # Für spätere Nutzung: Index zurücksetzen
            remapped_reset = remapped.reset_index()
            sanitized = FlowCalculator.sanitize_filename(flow_name)
            out_path = os.path.join(self.bottom_up_output_dir, f"{sanitized}_{cfg.tag}_flows.csv")
            remapped_reset.to_csv(out_path, index=False)
            logger.info("Gespeichert: %s", out_path)
            mapped[flow_name] = remapped_reset
        return mapped

    # ---------------- Residual Nachfrage + Stock ----------------
    def project_residual_demand(self, cfg: MaterialConfig):
        sanitized = FlowCalculator.sanitize_filename(cfg.bottom_up_to_stock_flow)
        bottom_up_fp = f"{self.bottom_up_output_dir}/{sanitized}_{cfg.tag}_flows.csv"
        self.flow_calc.project_demand(
            top_down_start_value_filepath=cfg.start_value_file,
            top_down_growth_rate_filepath=cfg.growth_rate_file,
            bottom_up_demand_filepath=bottom_up_fp,
            result_filepath=cfg.demand_future_file,
            material_column=cfg.product_column,
            default_sector=cfg.default_sector,
            default_region=cfg.default_region,
            default_material=None,
            base_year=self.base_year
        )
        logger.info("Residual Nachfrage projiziert -> %s", cfg.demand_future_file)
        if cfg.stock_model_config:
            run_eumfa(cfg.stock_model_config)

    # ---------------- Total Nachfrage ----------------
    def calculate_total_demand(self, cfg: MaterialConfig):
        sanitized = FlowCalculator.sanitize_filename(cfg.bottom_up_to_stock_flow)
        bottom_up_fp = f"{self.bottom_up_output_dir}/{sanitized}_{cfg.tag}_flows.csv"
        self.flow_calc.calculate_total_flows(
            bottom_up_filepath=bottom_up_fp,
            top_down_filepath=cfg.market_future_file,
            output_filepath=cfg.total_future_demand_file,
            default_region=cfg.default_region,
            bottom_up_end_use_sector=cfg.default_sector,
            product_column=cfg.product_column
        )
        logger.info("Total Nachfrage berechnet -> %s", cfg.total_future_demand_file)

    # ---------------- EOL ----------------
    def store_future_eol(self, cfg: MaterialConfig):
        if not cfg.eol_future_file or not cfg.total_future_eol_file:
            return
        try:
            df = pd.read_csv(cfg.eol_future_file)
            df.to_csv(cfg.total_future_eol_file, index=False)
            logger.info("Future EOL gespeichert -> %s", cfg.total_future_eol_file)
        except Exception as e:
            logger.error("Fehler beim Speichern Future EOL: %s", e)

    # ---------------- Downstream ----------------
    def run_downstream_flows(self, cfg: MaterialConfig):
        if cfg.flows_model_config:
            run_eumfa(cfg.flows_model_config)

    # ---------------- Historic + Future kombinieren ----------------
    def combine_historic_future(self, results_folder: str):
        historic_files = glob.glob(os.path.join(results_folder, "*historic*.csv"))
        if not historic_files:
            logger.warning("Keine historic Dateien in %s", results_folder)
            return
        for historic in historic_files:
            future = historic.replace("historic", "future")
            if not os.path.exists(future):
                logger.warning("Future Datei fehlt für %s", historic)
                continue
            combined = None
            try:
                hist_df = pd.read_csv(historic)
                fut_df = pd.read_csv(future)

                def clean(df: pd.DataFrame) -> pd.DataFrame:
                    drop_cols = [c for c in df.columns if c.lower().startswith("unnamed")]
                    if drop_cols:
                        df = df.drop(columns=drop_cols)
                    return df

                hist_df = clean(hist_df)
                fut_df = clean(fut_df)

                all_cols = sorted(set(hist_df.columns) | set(fut_df.columns))
                if not all_cols:
                    logger.warning("Dateien leer: %s / %s", historic, future)
                    continue

                for df in (hist_df, fut_df):
                    for c in all_cols:
                        if c not in df.columns:
                            df[c] = 0 if c == 'value' else 'Unknown'

                combined = pd.concat([hist_df[all_cols], fut_df[all_cols]], ignore_index=True)

                if 'value' in combined.columns:
                    key_cols = [c for c in all_cols if c != 'value']
                    if key_cols:
                        combined = combined.groupby(key_cols, as_index=False, dropna=False)['value'].sum()
                    else:
                        total_value = combined['value'].sum()
                        combined = pd.DataFrame([{'value': total_value}])
                        logger.info("Nur value-Spalte vorhanden, Gesamtwert aggregiert: %s", total_value)
                else:
                    logger.warning("Keine 'value' Spalte gefunden in %s / %s", historic, future)

                out_file = historic.replace("historic", "combined")
                combined.to_csv(out_file, index=False)
                logger.info("Kombiniert gespeichert -> %s", out_file)
            except Exception as e:
                logger.error("Fehler beim Kombinieren %s / %s: %s", historic, future, e)
            finally:
                if 'hist_df' in locals():
                    del hist_df
                if 'fut_df' in locals():
                    del fut_df
                if combined is not None:
                    del combined
                gc.collect()

    # ---------------- Pipeline ----------------
    def pipeline(self, cfg: MaterialConfig, run_bottom_up: bool, run_residual: bool, run_downstream: bool):
        if run_bottom_up:
            model_cfgs = []
            if cfg.sector == 'buildings':
                model_cfgs.append("config/buildings.yml")
            flows = self.run_bottom_up_models(model_cfgs) if model_cfgs else {}
            self.map_and_store_flows(flows, cfg)
        if run_residual:
            self.project_residual_demand(cfg)
            self.calculate_total_demand(cfg)
            self.store_future_eol(cfg)
        if run_downstream:
            self.run_downstream_flows(cfg)
            if cfg.flow_results_folder:
                self.combine_historic_future(cfg.flow_results_folder)

#------------------------------------------------------------------------------
# Material-spezifische Konfigurations-Erstellung
#------------------------------------------------------------------------------

def build_material_configs() -> List[MaterialConfig]:
    configs: List[MaterialConfig] = []
    # Concrete
    if "concrete" in materials_to_consider and "buildings" in bottom_up_sectors_to_consider:
        mf = MAPPING_FILES.get(("buildings", "concrete"))
        if mf:
            stock_dir = "data/baseline_cement_stock_flows"
            configs.append(
                MaterialConfig(
                    material="concrete",
                    sector="buildings",
                    mapping_file=mf,
                    relevant_flows=[
                        "sysenv => Concrete stock in buildings",
                        "Concrete stock in buildings => sysenv"
                    ],
                    bottom_up_to_stock_flow="sysenv => Concrete stock in buildings",
                    stock_to_eol_flow="Concrete stock in buildings => sysenv",
                    tag="concrete",
                    product_column="Concrete product simple",
                    start_value_file=f"{stock_dir}/input/datasets/start_value.csv",
                    growth_rate_file=f"{stock_dir}/input/datasets/growth_rate.csv",
                    demand_future_file=f"{stock_dir}/input/datasets/demand_future.csv",
                    stock_model_config="config/cement_stock.yml",
                    flows_model_config="config/cement_flows.yml",
                    market_future_file=f"{stock_dir}/output/export/flows/concrete_market_future__end_use_stock_future.csv",
                    eol_future_file=f"{stock_dir}/output/export/flows/end_use_stock_future__cdw_collection_future.csv",
                    total_future_demand_file=f"{stock_dir}/input/datasets/total_future_demand.csv",
                    total_future_eol_file=f"{stock_dir}/input/datasets/total_future_eol_flows.csv",
                    flow_results_folder=f"{stock_dir}/output/export/flows"
                )
            )
    return configs

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------

def main():
    orchestrator = EUMFAOrchestrator(base_year=baseyear)
    run_bottom_up_flag = not downstream_only
    run_residual_flag = not downstream_only
    run_downstream_flag = True
    for cfg in build_material_configs():
        orchestrator.pipeline(
            cfg=cfg,
            run_bottom_up=run_bottom_up_flag,
            run_residual=run_residual_flag,
            run_downstream=run_downstream_flag
        )
        logger.info("Pipeline für %s abgeschlossen", cfg.material)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Pipeline Fehler: %s", e)
        sys.exit(1)
    finally:
        sys.exit(0)
