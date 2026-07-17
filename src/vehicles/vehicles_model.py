import os

from src.common.common_cfg import GeneralCfg
from .vehicles_mfa_system import VehiclesMFASystem
from .vehicles_export import VehiclesDataExporter
from .vehicles_definition import get_definition

# todo übergabe hinzufügen (eol, material demand übergeben für kombiniertes modell)


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

        # Map the scenario switches onto the actual dataset file stems.
        # The default file stem for a parameter is just its name; the entries
        # below override that stem based on the chosen B/C/A (or named) variant.
        scenario_filenames = self._scenario_filenames()

        parameter_files = {}
        for parameter in self.definition.parameters:
            file_stem = scenario_filenames.get(parameter.name, parameter.name)
            parameter_files[parameter.name] = os.path.join(
                self.cfg.input_data_path, "datasets", f"{file_stem}.csv"
            )

        self.mfa = VehiclesMFASystem.from_csv(
            definition=self.definition,
            dimension_files=dimension_files,
            parameter_files=parameter_files,
            allow_missing_parameter_values=True,
            allow_extra_parameter_values=True,
        )
        self.mfa.cfg = self.cfg

    def _scenario_filenames(self):
        """Resolve the scenario switches in the config to dataset file stems.

        Returns a dict {parameter_name: file_stem}. Only parameters that are
        driven by a scenario switch appear here; everything else keeps its
        default file (handled by the caller).
        """
        sc = self.cfg.scenarios

        # For each scenario-driven parameter: {config value -> file stem}.
        options = {
            "vehicle_technology_share": {
                # downsizing measure
                "A": "vehicle_technology_share_A",    # ambitious
                "C": "vehicle_technology_share_C",    # conservative
                "B": "vehicle_technology_share_B",    # baseline
            },
            "vehicle_steel_intensity": {
                "B": "vehicle_steel_intensity_B",
                "HSS_A": "vehicle_steel_intensity_HSS_A",
                "HSS_C": "vehicle_steel_intensity_HSS_C",
                "Redesign_A": "vehicle_steel_intensity_Redesign_A",
                "Redesign_C": "vehicle_steel_intensity_Redesign_C",
            },
            "vehicle_steel_element_reuse": {
                # remanufacturing of steel
                "B": "vehicle_steel_element_reuse_B",
                "C": "vehicle_steel_element_reuse_combined_C",
                "A": "vehicle_steel_element_reuse_combined_A",
                # Strategy 1: remanufacturing of car panels
                "S1_C": "vehicle_steel_element_reuse_S1_C",
                "S1_A": "vehicle_steel_element_reuse_S1_A",
                # Strategy 2: remanufacturing of components
                "S2_C": "vehicle_steel_element_reuse_S2_C",
                "S2_A": "vehicle_steel_element_reuse_S2_A",
            },
        }

        # Which config switch drives which parameter.
        chosen = {
            "vehicle_technology_share": sc.technology_share,
            "vehicle_steel_intensity": sc.steel_intensity,
            "vehicle_steel_element_reuse": sc.steel_reuse,
        }

        resolved = {}
        for param_name, value in chosen.items():
            choices = options[param_name]
            if value not in choices:
                raise ValueError(
                    f"Invalid scenario value '{value}' for '{param_name}'. "
                    f"Valid options are: {list(choices.keys())}."
                )
            resolved[param_name] = choices[value]
        return resolved

    def run(self):
        self.mfa.compute()
        flows_as_dataframes = self.mfa.get_flows_as_dataframes()
        self.data_writer.export_mfa(mfa=self.mfa)
        self.data_writer.visualize_results(model=self)
        return flows_as_dataframes
