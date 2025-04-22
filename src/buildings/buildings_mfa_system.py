import flodym as fd


class BuildingsMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_flows()

    def compute_flows(self):
        prm = self.parameters
        flw = self.flows

        flw["sysenv => Steel stock in buildings"][...] = prm["building_inflow"] * prm["building_steel_intensity"]
        flw["sysenv => Concrete stock in buildings"][...] = prm["building_inflow"] * prm[
            "building_concrete_intensity"]
        flw["sysenv => Insulation stock in buildings"][...] = prm["building_inflow"] * prm[
            "building_insulation_intensity"]
        flw["sysenv => Glass stock in buildings"][...] = prm["building_inflow"] * prm["building_glass_intensity"]
        flw["Steel stock in buildings => sysenv"][...] = -prm["building_outflow"] * prm["building_steel_intensity"]
        flw["Concrete stock in buildings => sysenv"][...] = -prm["building_outflow"] * prm[
            "building_concrete_intensity"]
        flw["Insulation stock in buildings => sysenv"][...] = -prm["building_outflow"] * prm[
            "building_insulation_intensity"]
        flw["Glass stock in buildings => sysenv"][...] = -prm["building_outflow"] * prm[
            "building_glass_intensity"]
        flw["Steel stock in buildings => Steel stock in buildings"][...] = \
            flw["Steel stock in buildings => sysenv"] * prm["building_steel_element_reuse"]
        flw["sysenv => Steel stock in buildings"][...] = \
            flw["sysenv => Steel stock in buildings"] + \
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Steel stock in buildings => sysenv"][...] = \
            flw["Steel stock in buildings => sysenv"] -\
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Concrete stock in buildings => Concrete stock in buildings"][...] = \
            flw["Concrete stock in buildings => sysenv"] * prm["building_concrete_element_reuse"]
        flw["sysenv => Concrete stock in buildings"][...] = \
            flw["sysenv => Concrete stock in buildings"] + \
            flw["Concrete stock in buildings => Concrete stock in buildings"]
        flw["Concrete stock in buildings => sysenv"][...] = \
            flw["Concrete stock in buildings => sysenv"] - \
            flw["Concrete stock in buildings => Concrete stock in buildings"]

    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}