import os
from matplotlib import pyplot as plt
from src.common.base_model import EUMFABaseModel
import plotly.graph_objects as go
import flodym as fd
import flodym.export as fde

from src.common.common_cfg import VisualizationCfg


class CustomDataExporter(EUMFABaseModel):
    output_path: str
    do_export: dict = {"pickle": True, "csv": True}
    cfg: VisualizationCfg
    _display_names: dict = {}

    def export_mfa(self, mfa: fd.MFASystem):
        if self.do_export.get("pickle", False):
            fde.export_mfa_to_pickle(mfa=mfa, export_path=self.export_path("mfa.pickle"))
        if self.do_export.get("csv", False):
            dir_flows = os.path.join(self.export_path(), "flows")
            dir_stocks = os.path.join(self.export_path(), "stocks")
            # Keep flodym’s flow export
            fde.export_mfa_flows_to_csv(mfa=mfa, export_directory=dir_flows)
            # Use our own stock export to keep dimension columns (incl. Time)
            self._export_stocks_with_dims(mfa, dir_stocks)

    def _export_stocks_with_dims(self, mfa: fd.MFASystem, export_directory: str):
        os.makedirs(export_directory, exist_ok=True)
        for stock_name, stock in mfa.stocks.items():
            # Export the three standard arrays if present
            for field in ("stock", "inflow", "outflow"):
                arr = getattr(stock, field, None)
                if arr is None:
                    continue
                # arr supports to_df() with all dimension columns + 'value'
                df = arr.to_df()
                safe_name = stock_name.replace("=>", "_to_").replace(" ", "_")
                df.to_csv(os.path.join(export_directory, f"{safe_name}__{field}.csv"), index=False)

    def export_path(self, filename: str = None):
        path_tuple = (self.output_path, "export")
        if filename is not None:
            path_tuple += (filename,)
        return os.path.join(*path_tuple)

    def export_path(self, filename: str = None):
        path_tuple = (self.output_path, "export")
        if filename is not None:
            path_tuple += (filename,)
        return os.path.join(*path_tuple)

    def figure_path(self, filename: str):
        return os.path.join(self.output_path, "figures", filename)

    def _show_and_save_plotly(self, fig: go.Figure, name):
        if self.cfg.do_save_figs:
            fig.write_image(self.figure_path(f"{name}.png"))
        if self.cfg.do_show_figs:
            fig.show()

    def visualize_sankey(self, mfa: fd.MFASystem):
        plotter = fde.PlotlySankeyPlotter(
            mfa=mfa, display_names=self._display_names, **self.cfg.sankey
        )
        fig = plotter.plot()

        fig.update_layout(
            # title_text=f"Steel Flows ({', '.join([str(v) for v in self.sankey['slice_dict'].values()])})",
            font_size=20,
        )

        self._show_and_save_plotly(fig, name="sankey")

    def figure_path(self, filename: str) -> str:
        return os.path.join(self.output_path, "figures", filename)

    def plot_and_save_figure(self, plotter: fde.ArrayPlotter, filename: str, do_plot: bool = True):
        if do_plot:
            plotter.plot()
        if self.cfg.do_show_figs:
            plotter.show()
        if self.cfg.do_save_figs:
            plotter.save(self.figure_path(filename), width=2200, height=1300)

    def stop_and_show(self):
        if self.cfg.plotting_engine == "pyplot" and self.cfg.do_show_figs:
            plt.show()

    @property
    def plotter_class(self):
        if self.cfg.plotting_engine == "plotly":
            return fde.PlotlyArrayPlotter
        elif self.cfg.plotting_engine == "pyplot":
            return fde.PyplotArrayPlotter
        else:
            raise ValueError(f"Unknown plotting engine: {self.cfg.plotting_engine}")
