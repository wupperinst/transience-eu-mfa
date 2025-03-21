from src.common.base_model import EUMFABaseModel
import flodym as fd


IMPLEMENTED_MODELS = [
    "buildings",
    "vehicles",
]


def choose_sublass_by_name(name: str, parent: type) -> type:

    def recurse_subclasses(cls):
        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in recurse_subclasses(c)]
        )

    subclasses = {cls.__name__: cls for cls in recurse_subclasses(parent)}
    if name not in subclasses:
        raise ValueError(
            f"Subclass name for {parent.__name__} must be one of {list(subclasses.keys())}, but {name} was given."
        )
    return subclasses[name]


class VisualizationCfg(EUMFABaseModel):

    stock: dict = {"do_visualize": False}
    production: dict = {"do_visualize": False}
    sankey: dict = {"do_visualize": False}
    do_show_figs: bool = True
    do_save_figs: bool = False
    plotting_engine: str = "plotly"


class BuildingsVisualizationCfg(VisualizationCfg):

    pass


class VehiclesVisualizationCfg(VisualizationCfg):

    pass


class GeneralCfg(EUMFABaseModel):

    model_class: str
    input_data_path: str
    visualization: VisualizationCfg
    output_path: str
    do_export: dict[str, bool]

    @classmethod
    def from_model_class(cls, **kwargs) -> "GeneralCfg":
        if "model_class" not in kwargs:
            raise ValueError("model_class must be provided.")
        model_class = kwargs["model_class"]
        subclasses = {
            "buildings": BuildingsCfg,
            "vehicles": VehiclesCfg,
        }
        if model_class not in subclasses:
            raise ValueError(f"Model class {model_class} not supported.")
        subcls = subclasses[model_class]
        return subcls(**kwargs)


class BuildingsCfg(GeneralCfg):

    visualization: BuildingsVisualizationCfg


class VehiclesCfg(GeneralCfg):

    visualization: VehiclesVisualizationCfg

