"""Command: refresh the buildings parameters from the upstream MIC3 modules.

MIC3 (Model for European Industry Circularity and Climate Change Mitigation) is
the overall modelling framework; the EU MFA is a central module within it. This
command runs the interface that expresses what the upstream MIC3 modules supply
-- OPEN-GEM and the P&S database -- as the parameters the EU MFA buildings
sub-module reads. It runs no MFA of its own.

    python eumfa_mic3.py         # refresh the buildings parameters
    python eumfa_buildings.py    # run the EU MFA buildings sub-module
"""

import logging

import yaml

from src.mic3.mic3_model import Mic3Model

CFG_FILE = "config/mic3.yml"


def run_mic3(cfg_file: str = CFG_FILE):
    with open(cfg_file, "r") as stream:
        cfg = yaml.safe_load(stream)

    level = cfg.get("logging", {}).get("level", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    model = Mic3Model(cfg=cfg)
    return model.run()


if __name__ == "__main__":
    run_mic3()
