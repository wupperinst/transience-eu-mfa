import os
import logging

from src.common.common_cfg import GeneralCfg
from .plastics_mfa_system import PlasticsMFASystem
from .plastics_export import PlasticsDataExporter
from .plastics_definition import get_definition


class PlasticsModel:
    
    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = PlasticsDataExporter(
            cfg=self.cfg.visualization,
            do_export=self.cfg.do_export,
            selected_export=self.cfg.selected_export,
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
            "polymer": "polymers",
            "sector": f"end_use_sectors_{self.cfg.customization.end_use_sectors}",
            "waste_category": "waste_categories",
            "secondary_raw_material": "secondary_raw_materials",
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
        
        logging.info(f"model - Initializing PlasticsMFASystem.from_csv")
        self.mfa = PlasticsMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_missing_parameter_values=True,
            allow_extra_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def run(self):
        self.mfa.compute()
        logging.info("Model computations completed.")

        self.data_writer.export_mfa(mfa=self.mfa)
        
        logging.info("Exporting flows as dataframes.")
        flows_as_dataframes = self.mfa.get_flows_as_dataframes(flow_names=self.cfg.selected_export["csv_selected_flows"])
        
        #self.data_writer.export_selected_mfa_flows_to_csv(mfa=self.mfa, flow_names=self.cfg.selected_export["csv_selected_flows"])
        self.data_writer.visualize_results(model=self, flows_dfs=flows_as_dataframes, scenario=self.cfg.scenario)

        return flows_as_dataframes