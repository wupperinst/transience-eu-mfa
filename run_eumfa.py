import logging
import yaml
import flodym as fd


from src.common.common_cfg import GeneralCfg
from src.buildings.buildings_model import BuildingsModel
#from src.vehicles.vehicles_model import VehiclesModel
from src.plastics.plastics_model import PlasticsModel
from src.steel.steel_model import SteelModel
from src.cement_topdown.cement_topdown_model import CementTopdownModel
from src.cement_stock.cement_stock_model import CementStockModel
from src.cement_flows.cement_flows_model import CementFlowsModel

models = {
    "buildings": BuildingsModel,
#    "vehicles": VehiclesModel,
    "plastics": PlasticsModel,
    "steel": SteelModel,
    "cement_topdown": CementTopdownModel,
    "cement_stock" : CementStockModel,
    "cement_flows" : CementFlowsModel
}

def get_model_config(filename):
    with open(filename, "r") as stream:
        data = yaml.safe_load(stream)
    return {k: v for k, v in data.items()}


def init_mfa(cfg: dict) -> fd.MFASystem:
    """Choose MFA subclass and return an initialized instance."""

    cfg = GeneralCfg.from_model_class(**cfg)
    mfa = models[cfg.model_class](cfg=cfg)
    return mfa


def recalculate_mfa(model_config):
    mfa = init_mfa(cfg=model_config)
    logging.info(f"{type(mfa).__name__} instance created.")
    flows_as_dataframes = mfa.run()
    
    return flows_as_dataframes



def run_eumfa(cfg_file: str):
    model_config = get_model_config(cfg_file)

    try:
        logging_level = model_config['logging']['level'].upper()
    except KeyError:
        logging_level = "INFO"
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    flows_as_dataframes = recalculate_mfa(model_config)
    return flows_as_dataframes