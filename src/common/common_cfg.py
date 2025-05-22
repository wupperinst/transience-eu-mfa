from src.common.base_model import EUMFABaseModel
import flodym as fd


IMPLEMENTED_MODELS = [
    "buildings",
    "vehicles",
    "plastics",
    "steel",
    "cement_stock",
    "cement_flows",
]


def choose_subclass_by_name(name: str, parent: type) -> type:

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


class ModelCustomization(EUMFABaseModel):

    lifetime_model_name: str
    
    @property
    def lifetime_model(self) -> fd.LifetimeModel:
        return choose_subclass_by_name(self.lifetime_model_name, fd.LifetimeModel)

class PlasticsCustomizationCfg(ModelCustomization):
    
    end_use_sectors: str = "all"
    waste_not_for_recycling: list = []


class VisualizationCfg(EUMFABaseModel):

    stock: dict = {"do_visualize": False}
    inflow: dict = {"do_visualize": False}
    production: dict = {"do_visualize": False}
    sankey: dict = {"do_visualize": False}
    do_show_figs: bool = True
    do_save_figs: bool = False
    plotting_engine: str = "plotly"


class BuildingsVisualizationCfg(VisualizationCfg):

    pass

class VehiclesVisualizationCfg(VisualizationCfg):

    pass

class PlasticsVisualizationCfg(VisualizationCfg):

    inflow: dict = {"do_visualize": False}

class CementTopdownVisualizationCfg(VisualizationCfg):

    pass

class CementStockVisualizationCfg(VisualizationCfg):

    pass

class CementFlowsVisualizationCfg(VisualizationCfg):

    pass

class GeneralCfg(EUMFABaseModel):

    model_class: str
    input_data_path: str
    customization: ModelCustomization
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
            "plastics": PlasticsCfg,
            "steel": SteelCfg,
            "cement_stock": CementStockCfg,
            "cement_flows": CementFlowsCfg,
        }
        if model_class not in subclasses:
            raise ValueError(f"Model class {model_class} not supported.")
        subcls = subclasses[model_class]
        return subcls(**kwargs)


class BuildingsCfg(GeneralCfg):

    visualization: BuildingsVisualizationCfg

class VehiclesCfg(GeneralCfg):

    visualization: VehiclesVisualizationCfg

class PlasticsCfg(GeneralCfg):

    visualization: PlasticsVisualizationCfg
    customization: PlasticsCustomizationCfg

class SteelCfg(GeneralCfg):

    pass

class CementTopdownCfg(GeneralCfg):
    visualization: CementTopdownVisualizationCfg

class CementStockCfg(GeneralCfg):
    visualization: CementStockVisualizationCfg

class CementFlowsCfg(GeneralCfg):
    visualization: CementFlowsVisualizationCfg