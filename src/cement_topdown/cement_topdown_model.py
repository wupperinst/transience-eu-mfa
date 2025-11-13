# cement_topdown_model.py
import os
import logging
from src.common.common_cfg import GeneralCfg
from .cement_topdown_mfa_system import CementTopdownMFASystem
from src.cement_flows.cement_flows_export import CementFlowsDataExporter as CementTopdownDataExporter
from .cement_topdown_definition import get_definition

class CementTopdownModel:
    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = CementTopdownDataExporter(
            cfg=self.cfg.visualization,
            do_export=self.cfg.do_export,
            output_path=self.cfg.output_path,
        )
        self.init_mfa()

    def init_mfa(self):
        dimension_map = {
            "Time": "time_in_years",
            "Region simple": "regions_simple",
            "Concrete product simple": "concrete_products_simple",
            "Cement product": "cement_products",
            "Clinker product": "clinker_products",
            "End use sector": "end_use_sectors",
            "Concrete waste": "concrete_waste",
        }

        dimension_files = {
            dim.name: os.path.join(self.cfg.input_data_path, "dimensions", f"{dimension_map[dim.name]}.csv")
            for dim in self.definition.dimensions
        }
        parameter_files = {
            prm.name: os.path.join(self.cfg.input_data_path, "datasets", f"{prm.name}.csv")
            for prm in self.definition.parameters
        }

        self.mfa = CementTopdownMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_extra_parameter_values=True,
            allow_missing_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def get_flows_as_dataframes(self):
        return self.mfa.get_flows_as_dataframes()

    def run(self):
        self.mfa.compute()
        logging.info("Model computations completed.")

        logging.info("Exporting flows as dataframes.")
        flows_as_dataframes = self.mfa.get_flows_as_dataframes()
        
        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)

        return flows_as_dataframes