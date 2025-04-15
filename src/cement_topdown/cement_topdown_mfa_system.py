import flodym as fd

class CementTopdownMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_historic_stock()
        self.compute_future_stock()


    def compute_historic_stock(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        flw["Cement production => Cement market"][...] = prm["cement_production"]
        flw["Clinker market => Cement production"][...] = flw["Cement production => Cement market"] * \
            prm["clinker_factor"]
        flw["Clinker production => Clinker market"][...] = flw["Clinker market => Cement production"][...] - \
            prm["trade_clinker"]
        flw["Cement market => Concrete production"][...] = flw["Cement production => Cement market"][...] - \
            prm["trade_cement"]
        flw["Concrete production => Concrete market"][...] = flw["Cement market => Concrete production"][...] / \
            prm["cement_to_concrete"]
        flw["Concrete market => End use stock historic"][...] = (flw["Concrete production => Concrete market"][...] - \
            prm["trade_concrete"]) * prm["end_use_matrix"]
        stk["End use stock historic"].inflow[...] = flw["Concrete market => End use stock historic"][...]
        stk["End use stock historic"].lifetime_model.set_prms(
            mean=prm["end_use_lifetime_mean"], std=prm["end_use_lifetime_std"]
        )
        stk["End use stock historic"].compute()
        flw["End use stock historic => CDW collection"][...] = stk["End use stock historic"].outflow * \
            prm["dissipative_losses"]
        flw["CDW collection => CDW unsorted market"][...] = flw["End use stock historic => CDW collection"][...] * \
            prm["mapping_waste"]
        flw["CDW unsorted market => CDW separation"][...] = flw["CDW collection => CDW unsorted market"][...] - \
            prm["trade_CDW_unsorted"]
        flw["CDW separation => CDW sorted market"][...] = flw["CDW unsorted market => CDW separation"][...] * \
            prm["separation_efficiency"]
        flw["CDW sorted market => sysenv"][...] = flw["CDW separation => CDW sorted market"][...] - \
            prm["trade_CDW_sorted"]

    def compute_future_stock(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        flw["Concrete market => End use stock future"][...] = prm["start_value"] * prm["growth_rate"]
        flw["Concrete production => Concrete market"][...] = \
            flw["Concrete market => End use stock future"].sum_to(("t", "j", "f")) - prm["trade_concrete"]
        flw["Cement market => Concrete production"][...]= flw["Concrete production => Concrete market"] * \
            prm["cement_to_concrete"]
        flw["Cement production => Cement market"][...] = flw["Cement market => Concrete production"] - \
            prm["trade_cement"]
        flw["Clinker market => Cement production"][...] = flw["Cement production => Cement market"] * \
            prm["trade_clinker"]
        flw["Clinker production => Clinker market"][...] = flw["Clinker market => Cement production"] - \
            prm["trade_clinker"]
        stk["End use stock future"].inflow[...] = flw["Concrete market => End use stock future"][...]
        stk["End use stock future"].lifetime_model.set_prms(
            mean=prm["end_use_lifetime_mean"], std=prm["end_use_lifetime_std"]
        )
        stk["End use stock future"].compute()
        flw["End use stock future => CDW collection"][...] = stk["End use stock future"].outflow * \
                                                               prm["dissipative_losses"]
        flw["CDW collection => CDW unsorted market"][...] = flw["End use stock future => CDW collection"][...] * \
                                                            prm["mapping_waste"]
        flw["CDW unsorted market => CDW separation"][...] = flw["CDW collection => CDW unsorted market"][...] - \
                                                            prm["trade_CDW_unsorted"]
        flw["CDW separation => CDW sorted market"][...] = flw["CDW unsorted market => CDW separation"][...] * \
                                                          prm["separation_efficiency"]
        flw["CDW sorted market => sysenv"][...] = flw["CDW separation => CDW sorted market"][...] - \
                                                  prm["trade_CDW_sorted"]


    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}