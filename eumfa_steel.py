import argparse
from run_eumfa import run_eumfa

# ARGUMENTS
parser = argparse.ArgumentParser(description='Get scenario for steel sub-module.')
parser.add_argument('-s', '--scenario', dest='scenario', type=str, help='scenario names')
args = parser.parse_args()

# Scenario name
if args.scenario is None:
    scenario = 'baseline_pd'
else:
    scenario = args.scenario

# Run EUMFA with the specified scenario
cfg_file = f"config/steel_{scenario}.yml"
run_eumfa(cfg_file)

