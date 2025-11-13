import os
import logging
from src.common.common_cfg import GeneralCfg
from .cement_flows_mfa_system import CementFlowsMFASystem
from .cement_flows_export import CementFlowsDataExporter
from .cement_flows_definition import get_definition


class CementFlowsModel:

    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = CementFlowsDataExporter(
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
        self.mfa = CementFlowsMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_extra_parameter_values=True,
            allow_missing_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return self.mfa.get_flows_as_dataframes()

    def run(self):
        self.mfa.compute()
        logging.info("Model computations completed.")

        logging.info("Exporting flows as dataframes.")
        flows_as_dataframes = self.mfa.get_flows_as_dataframes()

        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)

        return flows_as_dataframes