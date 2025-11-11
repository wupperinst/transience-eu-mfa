import flodym as fd
from typing import TYPE_CHECKING

from src.common.custom_export import CustomDataExporter

if TYPE_CHECKING:
    from src.cement_stock.cement_stock_model import CementStockMFASystem


class CementStockDataExporter(CustomDataExporter):

    # Dictionary of variable names vs names displayed in figures. Used by visualization routines.
    _display_names: dict = {
        "Environment",
        "Clinker production",
        "Clinker market",
        "Cement production",
        "Cement market",
        "Concrete production",
        "Concrete market",
        "End use stock",
        "CDW collection",
        "CDW unsorted market",
        "CDW separation",
        "CDW sorted market",
    }

    def visualize_results(self, model: "CementStockMFASystem"):
        if self.cfg.inflow["do_visualize"]:
            self.visualize_inflow(mfa=model.mfa)
            self.stop_and_show()

    def visualize_inflow(self, mfa: fd.MFASystem):
        ap_modeled = self.plotter_class(
            array=mfa.inflow["Region simple"].sum_over(("f","s")),
            intra_line_dim="Time",
            line_label="Modeled",
            display_names=self._display_names,
        )
        fig = ap_modeled.plot()
        self.plot_and_save_figure(fig, "inflow.png")