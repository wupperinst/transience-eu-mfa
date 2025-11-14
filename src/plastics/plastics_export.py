import plotly.express as px
import pandas as pd
import flodym as fd
from typing import TYPE_CHECKING

from src.common.custom_export import CustomDataExporter

if TYPE_CHECKING:
    from src.plastics.plastics_model import PlasticsModel


class PlasticsDataExporter(CustomDataExporter):

    # Dictionary of variable names vs names displayed in figures. Used by visualization routines.
    _display_names: dict = {

    }

    def visualize_results(self, model: "PlasticsModel", flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        figs = []
        if self.cfg.inflow["do_visualize"]:
            #print("Inflow visualization not implemented yet.")
            fig = self.visualize_inflow(flows_dfs=flows_dfs, scenario=scenario)
            figs.append(fig)
        if self.cfg.production["do_visualize"]:
            #print("Production visualization not implemented yet.")
            fig = self.visualize_production(flows_dfs=flows_dfs, scenario=scenario)
            figs.append(fig)
        if self.cfg.stock["do_visualize"]:
            print("Stock visualization not implemented yet.")
            # self.visualize_stock(mfa=mfa)
        if self.cfg.outflow["do_visualize"]:
            #print("Outflow visualization not implemented yet.")
            fig = self.visualize_outflow(flows_dfs=flows_dfs, scenario=scenario)
            figs.append(fig)
        if self.cfg.sankey["do_visualize"]:
            self.visualize_sankey(mfa=model.mfa)
        self.stop_and_show(figs=figs)

    def stop_and_show(self, figs: list = None):
        if figs is not None:
            for fig in figs:
                fig.show()

    def visualize_inflow(self, flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        df = flows_dfs.get("Plastics market => End use stock")
        df.reset_index(inplace=True)
        fig = px.area(df.loc[df['region']=="EU27+3", ['time', 'sector', 'polymer', 'value']], 
                        x="time", y="value", line_group="polymer", color="sector",
                        labels={"value":"Final demand [t]"},
                        title="Plastics Inflow by Sector and Polymer in EU27+3",
                        subtitle=f"Scenario: {scenario}")
        return fig

    def visualize_production(self, flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        df = flows_dfs.get("sysenv => Polymer market")
        df.reset_index(inplace=True)
        fig = px.area(df.loc[df['region']=="EU27+3", ['time', 'sector', 'polymer', 'value']], 
                        x="time", y="value", line_group="polymer", color="sector",
                        labels={"value":"Converter demand [t]"},
                        title="Plastics Production by Sector and Polymer in EU27+3",
                        subtitle=f"Scenario: {scenario}")
        return fig
    
    def visualize_outflow(self, flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        df = flows_dfs.get("Waste collection => Waste sorting")
        df.reset_index(inplace=True)
        fig = px.area(df.loc[df['region']=="EU27+3", ['time', 'sector', 'polymer', 'value']], 
                        x="time", y="value", line_group="polymer", color="sector",
                        labels={"value":"Collected plastic waste [t]"},
                        title="Plastics Outflow by Sector and Polymer in EU27+3",
                        subtitle=f"Scenario: {scenario}")
        return fig