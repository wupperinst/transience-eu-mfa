import os
import logging

from src.common.common_cfg import GeneralCfg
from .steel_mfa_system import SteelMFASystem
from .steel_export import SteelDataExporter
from .steel_definition import get_definition


class SteelModel:
    
    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = SteelDataExporter(
            cfg=self.cfg.visualization,
            do_export=self.cfg.do_export,
            output_path=self.cfg.output_path,
        )
        self.init_mfa()

    def init_mfa(self):

        dimension_map = {
            "time": "time_in_years",
            "age-cohort": "age_cohorts",
            "element": "elements",
            "region": "regions",
            "other_region": "regions",
            "intermediate": "intermediates",
            "product": "products",
            "sector": "end_use_sectors",
            "waste_category": "waste_categories",
        }

        dimension_files = {}
        for dimension in self.definition.dimensions:
            dimension_filename = dimension_map[dimension.name]
            dimension_files[dimension.name] = os.path.join(
                self.cfg.input_data_path, "dimensions", f"{dimension_filename}.csv"
            )

        parameter_files = {}
        for parameter in self.definition.parameters:
            parameter_files[parameter.name] = os.path.join(
                self.cfg.input_data_path, "datasets", f"{parameter.name}.csv"
            )
        
        logging.info(f"model - Initializing SteelMFASystem.from_csv")
        self.mfa = SteelMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_missing_parameter_values=True,
            allow_extra_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def run(self):
        self.mfa.compute()
        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)