import flodym as fd
from typing import TYPE_CHECKING

from src.common.custom_export import CustomDataExporter

if TYPE_CHECKING:
    from src.vehicles.vehicles_model import VehiclesModel


class VehiclesDataExporter(CustomDataExporter):

    # Dictionary of variable names vs names displayed in figures. Used by visualization routines.
    _display_names: dict = {
        "Environment",
        "Vehicle stock",
        "Steel stock in vehicles",
        "Plastics stock in vehicles",
        "Glass stock in vehicles",
    }

    def visualize_results(self, model: "VehiclesModel"):
        if self.cfg.inflow["do_visualize"]:
            self.visualize_inflow(mfa=model.mfa)
            self.stop_and_show()

    def visualize_inflow(self, mfa: fd.MFASystem):
        ap_modeled = self.plotter_class(
            array=mfa.inflow["Region"].sum_over(("v","z")),
            intra_line_dim="Time",
            line_label="Modeled",
            display_names=self._display_names,
        )
        fig = ap_modeled.plot()
        self.plot_and_save_figure(fig, "inflow.png")