import flodym as fd
from typing import TYPE_CHECKING

from src.common.custom_export import CustomDataExporter

if TYPE_CHECKING:
    from src.buildings.buildings_model import BuildingsModel


class BuildingsDataExporter(CustomDataExporter):

    # Dictionary of variable names vs names displayed in figures. Used by visualization routines.
    _display_names: dict = {
        "Environment",
        "Building stock",
        "Steel stock in buildings",
        "Concrete stock in buildings",
        "Insulation stock in building",
        "Glass stock in buildings",
    }