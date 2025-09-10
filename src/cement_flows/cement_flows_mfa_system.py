import flodym as fd

class CementFlowsMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_historic_stock()
        self.compute_future_flows()


    def compute_historic_stock(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        flw["Cement production historic => Cement market historic"][...] = prm["cement_production"]
        flw["Clinker market historic => Cement production historic"][...] = (
            flw["Cement production historic => Cement market historic"] * prm["clinker_factor"]
        ).sum_to(("t", "j", "y"))
        flw["Clinker production historic => Clinker market historic"][...] = \
            flw["Clinker market historic => Cement production historic"][...] - prm["trade_clinker"]
        flw["Cement market historic => Concrete production historic"][...] = \
            flw["Cement production historic => Cement market historic"][...] - prm["trade_cement"]
        flw["Concrete production historic => Concrete market historic"][...] = \
            flw["Cement market historic => Concrete production historic"][...] * prm["cement_to_concrete_historic"]
        flw["Concrete market historic => End use stock historic"][...] = \
            (flw["Concrete production historic => Concrete market historic"][...] -
             prm["trade_concrete"]) * prm["end_use_matrix"]
        stk["End use stock historic"].inflow[...] = \
            flw["Concrete market historic => End use stock historic"][...]
        stk["End use stock historic"].lifetime_model.set_prms(
            mean=prm["end_use_lifetime_mean"], std=prm["end_use_lifetime_std"]
        )
        stk["End use stock historic"].compute()
        flw["End use stock historic => CDW collection historic"][...] = stk["End use stock historic"].outflow * \
            prm["dissipative_losses"]
        #  todo:      flw["End use stock historic => CDW collection historic"][...] = (stk["End use stock historic"].outflow - outflows from buildings from historic stocks in baseline scenario +
        #        outflows from buildings from histroic stock in any other scernario) * \ prm["dissipative_losses"]
        flw["CDW collection historic => CDW unsorted market historic"][...] = \
            flw["End use stock historic => CDW collection historic"][...] * prm["mapping_waste"]
        flw["CDW unsorted market historic => CDW separation historic"][...] = \
            flw["CDW collection historic => CDW unsorted market historic"][...] - prm["trade_CDW_unsorted"]
        flw["CDW separation historic => CDW sorted market historic"][...] = \
            flw["CDW unsorted market historic => CDW separation historic"][...] * prm["separation_efficiency"]
        flw["CDW sorted market historic => sysenv historic"][...] = \
            flw["CDW separation historic => CDW sorted market historic"][...] - prm["trade_CDW_sorted"]

    def compute_future_flows(self):
        prm = self.parameters
        flw = self.flows

        #start inflows and outflows from eumfa_combined to determine flw["Concrete market future => End use stock future"] and flw["End use stock future => CDW collection future"]
        flw["Concrete market future => End use stock future"][...] = prm["total_future_demand"]
        flw["End use stock future => CDW collection future"][...] = prm["total_future_eol_flows"]
        flw["Concrete production future => Concrete market future"][...] = \
            flw["Concrete market future => End use stock future"].sum_to(("t", "j", "f")) - prm["trade_concrete"]
        flw["Cement market future => Concrete production future"][...]= \
            flw["Concrete production future => Concrete market future"] * prm["cement_to_concrete_future"]
        flw["Cement production future => Cement market future"][...] = \
            flw["Cement market future => Concrete production future"] - prm["trade_cement"]
        flw["Clinker market future => Cement production future"][...] = (
            flw["Cement production future => Cement market future"] * prm["clinker_factor"]
        ).sum_to(("t", "j", "y"))
        flw["Clinker production future => Clinker market future"][...] = (
            flw["Clinker market future => Cement production future"] - prm["trade_clinker"]
        )
        flw["CDW collection future => CDW unsorted market future"][...] = \
            flw["End use stock future => CDW collection future"][...] * prm["mapping_waste"]
        flw["CDW unsorted market future => CDW separation future"][...] = \
            flw["CDW collection future => CDW unsorted market future"][...] - prm["trade_CDW_unsorted"]
        flw["CDW separation future => CDW sorted market future"][...] = \
            flw["CDW unsorted market future => CDW separation future"][...] * prm["separation_efficiency"]
        flw["CDW sorted market future => sysenv future"][...] = \
            flw["CDW separation future => CDW sorted market future"][...] - prm["trade_CDW_sorted"]


    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        print("Cement flows calculated")
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}