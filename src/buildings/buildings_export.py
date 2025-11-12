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
        "Insulation stock in buildings",
        "Glass stock in buildings",
    }

    def visualize_results(self, model: "BuildingsModel"):
        if self.cfg.inflow["do_visualize"]:
            self.visualize_inflow(mfa=model.mfa)
            self.stop_and_show()

    def visualize_inflow(self, mfa: fd.MFASystem):
        ap_modeled = self.plotter_class(
            array=mfa.inflow["Region"].sum_over(("b","a")),
            intra_line_dim="Time",
            line_label="Modeled",
            display_names=self._display_names,
        )
        fig = ap_modeled.plot()
        self.plot_and_save_figure(fig, "inflow.png")