import logging
import yaml
import flodym as fd

from src.common.common_cfg import GeneralCfg
from src.buildings.buildings_model import BuildingsModel
from src.vehicles.vehicles_model import VehiclesModel
from src.plastics.plastics_model import PlasticsModel

models = {
    "buildings": BuildingsModel,
    "vehicles": VehiclesModel,
    "plastics": PlasticsModel,
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
    mfa.run()
    logging.info("Model computations completed.")


def run_eumfa(cfg_file: str):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    model_config = get_model_config(cfg_file)
    recalculate_mfa(model_config)