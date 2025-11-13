import os
import logging
from matplotlib import pyplot as plt
from src.common.base_model import EUMFABaseModel
import plotly.graph_objects as go
import flodym as fd
import flodym.export as fde

from src.common.common_cfg import VisualizationCfg


class CustomDataExporter(EUMFABaseModel):
    output_path: str
    do_export: dict = {"pickle": True, "csv": True}
    selected_export: dict = {"csv_selected_flows": []} # list of flow names to export to csv
    cfg: VisualizationCfg
    _display_names: dict = {}

    def export_mfa(self, mfa: fd.MFASystem):
        if self.do_export["pickle"]:
            fde.export_mfa_to_pickle(mfa=mfa, export_path=self.export_path("mfa.pickle"))
        if self.do_export["csv"]:
            dir_out = os.path.join(self.export_path(), "flows")
            fde.export_mfa_flows_to_csv(mfa=mfa, export_directory=dir_out)
            fde.export_mfa_stocks_to_csv(mfa=mfa, export_directory=dir_out)

    def export_selected_mfa_flows_to_csv(self, mfa: fd.MFASystem, flow_names: list[str]):
        dir_out = os.path.join(self.export_path(), "flows")
        if not os.path.exists(dir_out):
            os.makedirs(dir_out)
        for flow_name in flow_names:
            try:
                flow = mfa.flows[flow_name]
                flow.to_df().to_csv(os.path.join(dir_out, f"{fde.helper.to_valid_file_name(flow_name)}.csv"))
            except KeyError:
                logging.INFO(f"Export to csv: flow '{flow_name}' not found in MFA system.")
                continue

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
