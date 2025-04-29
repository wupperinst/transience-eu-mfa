import os

from src.common.common_cfg import GeneralCfg
from .vehicles_mfa_system import VehiclesMFASystem
from .vehicles_export import VehiclesDataExporter
from .vehicles_definition import get_definition

#todo übergabe hinzufügen (eol, material demand übergeben für kombiniertes modell)

class VehiclesModel:

    def __init__(self, cfg: GeneralCfg):
        self.cfg = cfg
        self.definition = get_definition(cfg)
        self.data_writer = VehiclesDataExporter(
            cfg=self.cfg.visualization,
            do_export=self.cfg.do_export,
            output_path=self.cfg.output_path,
        )
        self.init_mfa()

    def init_mfa(self):

        dimension_map = {
            "Time": "time_in_years",
            "Region": "regions",
            "Vehicle type": "vehicle_types",
            "Vehicle size": "vehicle_size",
            "Steel product": "steel_products",
            "Plastics product": "plastics_products",
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

        self.mfa = VehiclesMFASystem.from_csv(
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
