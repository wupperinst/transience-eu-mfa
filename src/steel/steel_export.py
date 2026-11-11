import plotly.express as px
import pandas as pd
import flodym as fd
from typing import TYPE_CHECKING

from src.common.custom_export import CustomDataExporter

if TYPE_CHECKING:
    from src.steel.steel_model import SteelModel


class SteelDataExporter(CustomDataExporter):

    # Dictionary of variable names vs names displayed in figures. Used by visualization routines.
    _display_names: dict = {

    }

    def visualize_results(self, model: "SteelModel", flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        if self.cfg.inflow["do_visualize"]:
            print("Inflow visualization not implemented yet.")
            # self.visualize_inflow(mfa=model.mfa)
        if self.cfg.stock["do_visualize"]:
            print("Stock visualization not implemented yet.")
            # self.visualize_stock(mfa=mfa)
        if self.cfg.sankey["do_visualize"]:
            self.visualize_sankey(mfa=model.mfa)
        self.stop_and_show()
        if self.cfg.dashboard["do_visualize"]:
            #print("Dashboard visualization not implemented yet.")
            self.visualize_dashboard(flows_dfs=flows_dfs, scenario=scenario)
    
    ## Build a dashboard with Dash

    def visualize_flow(self, df: pd.DataFrame, scenario: str = "", region: str = "EU27+1", select_col: str = "sector", label_type: str = "production"):
        #df.reset_index(inplace=True, drop=True)
        if label_type != "scrap":
            line_group = "sector" if select_col == "product" else "product"
            dimensions = ["time", "sector", "product", "value"]
        else:
            line_group = None
            dimensions = ["time", "waste_category", "value"]

        labels = {"production": {"y_label":"Domestic production [t]", "title": f"Steel Production by Sector and Product in {region}"},
                  "final_demand": {"y_label":"Final demand [t]", "title": f"Steel Inflow by Sector and Product in {region}"},
                  "outflow": {"y_label":"Collected steel waste [t]", "title": f"Steel Outflow by Sector and Product in {region}"},
                  "scrap": {"y_label":"Available scrap [t]", "title": f"Available sorted steel scrap by waste category and element in {region}"}}
        df = df.loc[df['element']=='All']
        fig = px.area(df.loc[df['region']==region, dimensions], 
                        x="time", y="value", line_group=line_group, color=select_col,
                        labels={"value":labels[label_type]["y_label"]},
                        title=labels[label_type]["title"],
                        subtitle=f"Scenario: {scenario}")
        return fig

    def build_table(self, df: pd.DataFrame, data_type: dict):
        from dash import dash_table

        table = dash_table.DataTable(
                    columns=[
                        {'name': i, 'id': i, 'type': data_type[i]} for i in df.columns
                    ],
                    data=df.to_dict('records'),
                    filter_action='native',

                    css=[{
                        'selector': 'table',
                        'rule': 'table-layout: fixed'  # note - this does not work with fixed_rows
                    }],
                    page_size=20,  # For tables >1000 rows, pagination is better for performance
                    #fixed_rows={'headers': True},
                    style_table={'height': '400px', 'overflowY': 'auto'},
                    style_data={
                        'width': '{}%'.format(100. / len(df.columns)),
                        'textOverflow': 'hidden'
                    }
                )
        return table

    def visualize_dashboard(self, flows_dfs: dict[str, pd.DataFrame], scenario: str = ""):
        from dash import Dash, html, dcc, dash_table, callback, Output, Input
        import dash_ag_grid as dag

        app = Dash()
        # Requires Dash 2.17.0 or later

        # Get data
        dfs = {}
        dfs['final_demand'] = flows_dfs.get("Steel goods market => End use stock")
        dfs['final_demand'].reset_index(inplace=True, drop=False)
        dfs['production'] = flows_dfs.get("sysenv => Steel product market")
        dfs['production'].reset_index(inplace=True, drop=False)
        dfs['outflow'] = flows_dfs.get("End use stock => Waste management")
        dfs['outflow'].reset_index(inplace=True, drop=False)
        dfs['scrap'] = flows_dfs.get("Waste management => AVAILABLE SCRAP sysenv")
        dfs['scrap'].reset_index(inplace=True, drop=False)

        data_type = {'time': 'numeric', 'age-cohort': 'numeric', 'region': 'text', 
                     'sector': 'text', 'intermediate': 'text', 'product': 'text', 'element': 'text', 
                     'waste_category': 'text',
                     'value': 'numeric'}
        
        regions = dfs['final_demand']['region'].unique().tolist()

        # Prepare tables
        table_production = self.build_table(df=dfs['production'], data_type=data_type)
        table_final_demand = self.build_table(df=dfs['final_demand'], data_type=data_type)
        table_outflow = self.build_table(df=dfs['outflow'], data_type=data_type)
        table_scrap = self.build_table(df=dfs['scrap'], data_type=data_type)
    
        # App layout
        app.layout = [
            # header
            html.Div(children=f'EU-MFA Steel Dashboard - {scenario} scenario', style={'fontSize': 30, 'textAlign': 'center'}),
            html.Br(),
            html.Br(),

            # GRAPHS
            html.Div(children=f'Graphs', style={'fontSize': 25, 'textAlign': 'left'}),
            html.Br(),
            #dcc.Graph(figure=figs['production']),
            dcc.RadioItems(options=['sector', 'product'], value='sector', id='controls-button-production'),
            dcc.Dropdown(options=regions, value='EU27+1', placeholder="Select a region", id='dropdown-production'),
            dcc.Graph(figure={}, id='controls-graph-production'),
            #dcc.Graph(figure=figs['final_demand']),
            dcc.RadioItems(options=['sector', 'product'], value='sector', id='controls-button-final-demand'),
            dcc.Dropdown(options=regions, value='EU27+1', placeholder="Select a region", id='dropdown-final-demand'),
            dcc.Graph(figure={}, id='controls-graph-final_demand'),
            #dcc.Graph(figure=figs['outflow']),
            dcc.RadioItems(options=['sector', 'product'], value='sector', id='controls-button-outflow'),
            dcc.Dropdown(options=regions, value='EU27+1', placeholder="Select a region", id='dropdown-outflow'),
            dcc.Graph(figure={}, id='controls-graph-outflow'),
            #dcc.Graph(figure=figs['scrap']),
            dcc.RadioItems(options=['waste_category'], value='waste_category', id='controls-button-scrap'),
            dcc.Dropdown(options=regions, value='EU27+1', placeholder="Select a region", id='dropdown-scrap'),
            dcc.Graph(figure={}, id='controls-graph-scrap'),

            html.Br(),
            html.Br(),

            # TABLES
            html.Div(children=f'Tables', style={'fontSize': 25, 'textAlign': 'left'}),
            html.Br(),
            #dag.AgGrid(
            #    rowData=dfs['final_demand'].to_dict('records'),
            #    columnDefs=[{"field": i} for i in dfs['final_demand'].columns]
            #),

            # Production table
            html.Div(children=f'Production', style={'fontSize': 20, 'textAlign': 'left'}),
            table_production,
            html.Br(),
            # Final demand table
            html.Div(children=f'Final demand', style={'fontSize': 20, 'textAlign': 'left'}),
            table_final_demand,
            html.Br(),
            # Outflow table
            html.Div(children=f'Outflow', style={'fontSize': 20, 'textAlign': 'left'}),
            table_outflow,
            html.Br(),
            # Scrap table
            html.Div(children=f'Available scrap', style={'fontSize': 20, 'textAlign': 'left'}),
            table_scrap,
        ]

        # Add controls to build the interaction
        @callback(
            Output(component_id='controls-graph-production', component_property='figure'),
            [Input(component_id='controls-button-production', component_property='value')
             ,Input(component_id='dropdown-production', component_property='value')]
        )
        def update_graph(col_chosen, region_chosen):
            fig = self.visualize_flow(df=dfs['production'], scenario=scenario, 
                                      select_col=col_chosen, region=region_chosen, label_type="production")
            return fig
        
        @callback(
            Output(component_id='controls-graph-final_demand', component_property='figure'),
            [Input(component_id='controls-button-final-demand', component_property='value')
             ,Input(component_id='dropdown-final-demand', component_property='value')]
        )
        def update_graph(col_chosen, region_chosen):
            fig = self.visualize_flow(df=dfs['final_demand'], scenario=scenario, 
                                      select_col=col_chosen, region=region_chosen, label_type="final_demand")
            return fig
        
        @callback(
            Output(component_id='controls-graph-outflow', component_property='figure'),
            [Input(component_id='controls-button-outflow', component_property='value')
             ,Input(component_id='dropdown-outflow', component_property='value')]
        )
        def update_graph(col_chosen, region_chosen):
            fig = self.visualize_flow(df=dfs['outflow'], scenario=scenario, 
                                      select_col=col_chosen, region=region_chosen, label_type="outflow")
            return fig
        
        @callback(
            Output(component_id='controls-graph-scrap', component_property='figure'),
            [Input(component_id='controls-button-scrap', component_property='value')
             ,Input(component_id='dropdown-scrap', component_property='value')]
        )
        def update_graph(col_chosen, region_chosen):
            fig = self.visualize_flow(df=dfs['scrap'], scenario=scenario, 
                                      select_col=col_chosen, region=region_chosen, label_type="scrap")
            return fig

        app.run(debug=True)
