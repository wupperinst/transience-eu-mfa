import flodym as fd

class CementTopdownMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_future_stock()

    def compute_future_stock(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Start value and growth rate for future inflow from eumfa_combined to determine flw["Concrete market future => End use stock future"]
        flw["Concrete market future => End use stock future"][...] = prm["demand_future"]
        stk["End use stock future"].inflow[...] = flw["Concrete market future => End use stock future"][...]
        stk["End use stock future"].lifetime_model.set_prms(
            mean=prm["end_use_lifetime_mean"], std=prm["end_use_lifetime_std"]
        )
        stk["End use stock future"].compute()
        flw["End use stock future => CDW collection future"][...] = stk["End use stock future"].outflow * \
                                                               prm["dissipative_losses"]

    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}