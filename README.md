# TRANSIENCE EU MFA module
*This repo displays the status of development for the EU MFA module within the TRANSIENCE project (Task 4.3).*

The EU MFA module is a multi-regional dynamic Material Flow Analysis (MFA) of the basic materials steel, plastics and cement. 
It is able to combine bottom-up approaches for buildings and vehicles with top-down approaches for steel, plastics and cement.

The EU MFA is planned to be one module in a larger framework developed within the [TRANSIENCE (TRANSItioning towards an Efficient, carbon-Neutral Circular European industry) project](https://www.transience.eu/).

## Acknowledgements
The module development is funded from the European Union’s Horizon programme under Grant Agreement No. 101137606 (TRANSIENCE). 
The responsibility for the content lies solely with the contributors.

The basic version of the building module has been developed as part of the Horizon project [newTRENDs](https://github.com/H2020-newTRENDs/flow).

The module is built with the framework [flodym (Flexibe Open Dynamic Material Systems Model)](https://github.com/pik-piam/flodym).

## Installation
 - Download the code from this repository or `git clone` it.
 - Install the requirements in a [python virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/).
 - Run `python3 src/eumfa_SUBMODULE.py` from the repo's folder where you replace *SUBMODULE* with the name of one of the bottom-up (*vehicles* or *buildings*) or top-down (*plastics*, *steel*, or *cement_topdown*) MFA models. The sub-module *combined* integrates the *buildings* and *cement_topdown* models (under development for other materials).


 <!-- stop parsing here on readthedocs -->

## Documentation
A preliminary documentation of the module is available on [readthedocs](https://transience-eu-mfa.readthedocs.io/en/latest/).

## License
[TRANSIENCE EU MFA](https://github.com/wupperinst/transience-eu-mfa) © 2025 by [Wuppertal Institute for climate, environment and energy](https://wupperinst.org/) and [Fraunhofer ISI](https://www.isi.fraunhofer.de/en.html) is licensed under [GNU AGPL 3.0](https://www.gnu.org/licenses/agpl-3.0.html)
