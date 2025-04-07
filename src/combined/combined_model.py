import os

from src.common.common_cfg import GeneralCfg
from .buildings_mfa_system import BuildingsMFASystem
from .buildings_export import BuildingsDataExporter
from .buildings_definition import get_definition


class CombinedModel:

#todo adapt; map dimensions or preprocessing or adapt input data?

    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = BuildingsDataExporter(
            cfg=self.cfg.visualization,
            do_export=self.cfg.do_export,
            output_path=self.cfg.output_path,
        )
        self.init_mfa()

    def init_mfa(self):

        dimension_map = {
            "Time": "time_in_years",
            "Region": "regions",
            "Building type": "building_types",
            "Age cohort": "building_cohorts",
            "Steel product": "steel_products",
            "Concrete product": "concrete_products",
            "Insulation product": "insulation_products",
            "Glass product": "glass_products",
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
        self.mfa = BuildingsMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_extra_parameter_values=True,
            allow_missing_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def run(self):
        self.mfa.compute()
        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)
