import flodym as fd


class VehiclesMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_flows()

    def compute_flows(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stock

        flw["Environment => Vehicle stock"][...] = prm["vehicle_inflow"] * prm["vehicle_technology_share"]
        flw["Environment => Steel stock in vehicles"][...] = flw["Environment => Vehicle stock"] * prm[
            "vehicles_steel_intensity"]
        flw["Environment => Plastics stock in vehicles"][...] = flw["Environment => Vehicle stock"] * prm[
            "vehicles_plastics_intensity"]
        flw["Environment => Glass stock in vehicles"][...] = flw["Environment => Vehicle stock"] * prm[
            "vehicles_glass_intensity"]
        stk["Steel stock in vehicles"].inflow[...] = flw["Environment => Steel stock in vehicles"]
        stk["Steel stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Steel stock in vehicles"].compute()
        stk["Plastics stock in vehicles"].inflow[...] = flw["Environment => Plastics stock in vehicles"]
        stk["Plastics stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Plastics stock in vehicles"].compute()
        stk["Glass stock in vehicles"].inflow[...] = flw["Environment => Glass stock in vehicles"]
        stk["Glass stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Glass stock in vehicles"].compute()
        flw["Steel stock in vehicles => Environment"][...] = stk["Steel stock in vehicles"].outflow
        flw["Plastics stock in vehicles => Environment"][...] = stk["Plastics stock in vehicles"].outflow
        flw["Glass stock in vehicles => Environment"][...] = stk["Glass stock in vehicles"].outflow
