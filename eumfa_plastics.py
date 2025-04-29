from run_eumfa import run_eumfa

import logging
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)

cfg_file = "config/plastics.yml"
run_eumfa(cfg_file)
