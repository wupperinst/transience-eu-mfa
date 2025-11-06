import argparse
import logging
from run_eumfa import run_eumfa


#logging.basicConfig(level=logging.INFO)

# ARGUMENTS
parser = argparse.ArgumentParser(description='Get scenario for plastics sub-module.')
parser.add_argument('-s', '--scenario', dest='scenario', type=str, help='scenario names')
args = parser.parse_args()

# Scenario name
if args.scenario is None:
    scenario = 'baseline'
else:
    scenario = args.scenario

# Run EUMFA with the specified scenario
cfg_file = f"config/plastics_{scenario}.yml"
run_eumfa(cfg_file)
