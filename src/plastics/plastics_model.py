import os
import logging

from src.common.common_cfg import GeneralCfg
from .plastics_mfa_system import PlasticsMFASystem
from .plastics_mfa_system_reuse import ReusePlasticsMFASystem
from .plastics_export import PlasticsDataExporter
from .plastics_definition import get_definition
from .plastics_definition_reuse import get_definition_reuse


class PlasticsModel:
    
    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        if self.cfg.customization.reuse:
            logging.info("Initializing model with reuse customization.")
            self.definition = get_definition_reuse(cfg)
        else:
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

        if self.cfg.customization.reuse:
            dimension_map["reuse_cycle"] = "reuse_cycles"
            dimension_map["mechanical_recycling_cycle"] = "mechanical_recycling_cycles"

        if self.cfg.customization.prodcom:
            dimension_map["product"] = f"products_{self.cfg.customization.end_use_sectors}"

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
        
        if not self.cfg.customization.reuse:
            logging.info(f"model - Initializing PlasticsMFASystem.from_csv")
            self.mfa = PlasticsMFASystem.from_csv(
                definition=self.definition,
                dimension_files=dimension_files,
                parameter_files=parameter_files,
                allow_missing_parameter_values=True,
                allow_extra_parameter_values=True,
            )
            self.mfa.cfg = self.cfg
        else:
            logging.info(f"model - Initializing ReusePlasticsMFASystem.from_csv")
            self.mfa = ReusePlasticsMFASystem.from_csv(
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

        #self.data_writer.export_mfa(mfa=self.mfa)
        
        logging.info("Exporting stock slices to csv.")
        # Export sliced stocks with age-cohort dimension
        self.data_writer.export_sliced_stocks_by_age_cohort_to_csv(
            mfa=self.mfa, 
            stock_names=self.cfg.selected_export["csv_selected_stocks"], 
            slice_dicts=self.cfg.selected_export["csv_slice_stocks"])
        # Export stock slices aggregating age-cohorts
        self.data_writer.export_sliced_stocks_to_csv(
            mfa=self.mfa, 
            stock_names=self.cfg.selected_export["csv_selected_stocks"], 
            slice_dicts=self.cfg.selected_export["csv_slice_stocks"])

        logging.info("Exporting flows as dataframes.")
        flows_as_dataframes = self.mfa.get_flows_as_dataframes(flow_names=self.cfg.selected_export["csv_selected_flows"])
        
        # logging.info("Aggregating flows along age-cohort.")
        # flows_as_dataframes = self.mfa.aggregate_flows_by_age_cohort(flows_as_dataframes, flow_names=self.cfg.selected_export["csv_selected_flows"])
        
        logging.info("Exporting flows to csv.")
        #self.data_writer.export_selected_mfa_flows_to_csv(mfa=self.mfa, flow_names=self.cfg.selected_export["csv_selected_flows"])
        self.data_writer.export_selected_flows_to_csv(flow_dfs=flows_as_dataframes, flow_names=self.cfg.selected_export["csv_selected_flows"])

        logging.info("Exporting parameters to csv.")
        os.makedirs(os.path.join(self.data_writer.output_path, "parameters"), exist_ok=True)
        for prm_name, prm_fd in self.mfa.parameters.items():
            prm_df = prm_fd.to_df(index=False, sparse=True)
            prm_df.to_csv(os.path.join(self.data_writer.output_path, "parameters", f"{prm_name}.csv"), index=False)

        logging.info("Visualizing results.")
        self.data_writer.visualize_results(model=self, flows_dfs=flows_as_dataframes, scenario=self.cfg.scenario)

        return flows_as_dataframes