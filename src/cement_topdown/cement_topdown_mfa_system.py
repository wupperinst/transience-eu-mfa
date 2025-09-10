# cement_topdown_mfa_system.py
import flodym as fd
from src.cement_flows.cement_flows_mfa_system import CementFlowsMFASystem as FlowsFuncs
from src.cement_stock.cement_stock_mfa_system import CementStockMFASystem as StockFuncs

class CementTopdownMFASystem(fd.MFASystem):
    def compute(self):
        self.compute_historic_chain()
        self.compute_future_chain()

    def compute_historic_chain(self):
        # Reuse the historic computation from cement_flows
        FlowsFuncs.compute_historic_stock(self)

    def compute_future_chain(self):
        prm, flw = self.parameters, self.flows

        # 1) Build demand_future internally (no CSV required)
        #    Fallback: use start_value * growth_rate already present in cement_topdown
        if "demand_future" not in prm:
            self.parameters["demand_future"] = prm["start_value"] * prm["growth_rate"]

        # 2) Run the existing stock function (fills future inflow and EOL flow)
        StockFuncs.compute_future_stock(self)

        # 3) Feed flows into the params expected by the flows function (no CSV required)
        if "total_future_demand" not in prm:
            self.parameters["total_future_demand"] = self.get_new_array(dim_letters=("t","j","f","s"))
        self.parameters["total_future_demand"][...] = flw["Concrete market future => End use stock future"][...]

        if "total_future_eol_flows" not in prm:
            self.parameters["total_future_eol_flows"] = self.get_new_array(dim_letters=("t","j","f","s"))
        self.parameters["total_future_eol_flows"][...] = flw["End use stock future => CDW collection future"][...]

        # 4) Run the existing future chain from cement_flows (correct clinker logic)
        FlowsFuncs.compute_future_flows(self)

    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}