import flodym as fd


class BuildingsMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_flows()

    def compute_flows(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stock

        flw["Environment => Steel stock in buildings"][...] = prm["building_inflow"]*prm["steel_intensity"]
        flw["Environment => Concrete stock in buildings"][...] = prm["building_inflow"] * prm["concrete_intensity"]
        flw["Environment => Insulation stock in buildings"][...] = prm["building_inflow"] * prm["insulation_intensity"]
        flw["Environment => Glass stock in buildings"][...] = prm["building_inflow"] * prm["glass_intensity"]
        flw["Steel stock in buildings => Environment"][...] = prm["building_outflow"] * prm["steel_intensity"]
        flw["Concrete stock in buildings => Environment"][...] = prm["building_outflow"] * prm["concrete_intensity"]
        flw["Insulation stock in buildings => Environment"][...] = prm["building_outflow"] * prm["insulation_intensity"]
        flw["Glass stock in buildings => Environment"][...] = prm["building_outflow"] * prm["glass_intensity"]
        stk["Steel stock in buildings"][...] = prm["building_stock"]*prm["steel_intensity"]
        stk["Concrete stock in buildings"][...] = prm["building_stock"] * prm["concrete_intensity"]
        stk["Insulation stock in buildings"][...] = prm["building_stock"] * prm["insulation_intensity"]
        stk["Glass stock in buildings"][...] = prm["building_stock"] * prm["glass_intensity"]
        flw["Steel stock in buildings => Steel stock in buildings"][...] = \
            flw["Steel stock in buildings => Environment"] * prm["steel_element_reuse"]
        flw["Environment => Steel stock in buildings"][...] = \
            flw["Environment => Steel stock in buildings"] + \
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Steel stock in buildings => Environment"][...] = \
            flw["Steel stock in buildings => Environment"] -\
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Concrete stock in buildings => Concrete stock in buildings"][...] = \
            flw["Concrete stock in buildings => Environment"] * prm["concrete_element_reuse"]
        flw["Environment => Concrete stock in buildings"][...] = \
            flw["Environment => Concrete stock in buildings"] + \
            flw["Concrete stock in buildings => Concrete stock in buildings"]
        flw["Concrete stock in buildings => Environment"][...] = \
            flw["Concrete stock in buildings => Environment"] - \
            flw["Concrete stock in buildings => Concrete stock in buildings"]