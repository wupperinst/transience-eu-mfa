import os

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
            output_path=self.cfg.output_path,
        )
        self.init_mfa()

    def init_mfa(self):

        dimension_map = {
            "time": "time_in_years",
            "Age-cohort": "age_cohorts",
            "element": "elements",
            "region": "regions",
            "other Region": "regions",
            "polymer": "polymers",
            "sector": "end_use_sectors",
            "Waste category": "waste_categories",
            "Secondary raw material": "secondary_raw_materials",
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
        self.mfa = PlasticsMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
        )
        self.mfa.cfg = self.cfg

    def run(self):
        self.mfa.compute()
        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)