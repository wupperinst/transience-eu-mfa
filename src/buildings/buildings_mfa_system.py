import flodym as fd


class BuildingsMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_flows()

    def compute_flows(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stock

        flw["Environment => Steel stock in buildings"][...] = prm["building_inflow"] * prm["buildings_steel_intensity"]
        flw["Environment => Concrete stock in buildings"][...] = prm["building_inflow"] * prm[
            "buildings_concrete_intensity"]
        flw["Environment => Insulation stock in buildings"][...] = prm["building_inflow"] * prm[
            "buildings_insulation_intensity"]
        flw["Environment => Glass stock in buildings"][...] = prm["building_inflow"] * prm["buildings_glass_intensity"]
        flw["Steel stock in buildings => Environment"][...] = prm["building_outflow"] * prm["buildings_steel_intensity"]
        flw["Concrete stock in buildings => Environment"][...] = prm["building_outflow"] * prm[
            "buildings_concrete_intensity"]
        flw["Insulation stock in buildings => Environment"][...] = prm["building_outflow"] * prm[
            "buildings_insulation_intensity"]
        flw["Glass stock in buildings => Environment"][...] = prm["building_outflow"] * prm[
            "buildings_glass_intensity"]
        stk["Steel stock in buildings"][...] = prm["building_stock"]*prm["buildings_steel_intensity"]
        stk["Concrete stock in buildings"][...] = prm["building_stock"] * prm["buildings_concrete_intensity"]
        stk["Insulation stock in buildings"][...] = prm["building_stock"] * prm["buildings_insulation_intensity"]
        stk["Glass stock in buildings"][...] = prm["building_stock"] * prm["buildings_glass_intensity"]
        flw["Steel stock in buildings => Steel stock in buildings"][...] = \
            flw["Steel stock in buildings => Environment"] * prm["buildings_steel_element_reuse"]
        flw["Environment => Steel stock in buildings"][...] = \
            flw["Environment => Steel stock in buildings"] + \
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Steel stock in buildings => Environment"][...] = \
            flw["Steel stock in buildings => Environment"] -\
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Concrete stock in buildings => Concrete stock in buildings"][...] = \
            flw["Concrete stock in buildings => Environment"] * prm["buildings_concrete_element_reuse"]
        flw["Environment => Concrete stock in buildings"][...] = \
            flw["Environment => Concrete stock in buildings"] + \
            flw["Concrete stock in buildings => Concrete stock in buildings"]
        flw["Concrete stock in buildings => Environment"][...] = \
            flw["Concrete stock in buildings => Environment"] - \
            flw["Concrete stock in buildings => Concrete stock in buildings"]