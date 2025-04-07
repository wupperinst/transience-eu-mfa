import flodym as fd


class VehiclesMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_flows()

    def compute_flows(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        flw["sysenv => Vehicle stock"][...] = prm["vehicle_inflow"] * prm["vehicle_technology_share"]
        flw["sysenv => Steel stock in vehicles"][...] = flw["sysenv => Vehicle stock"] * prm[
            "vehicle_steel_intensity"]
        flw["sysenv => Plastics stock in vehicles"][...] = flw["sysenv => Vehicle stock"] * prm[
            "vehicle_plastics_intensity"]
        flw["sysenv => Glass stock in vehicles"][...] = flw["sysenv => Vehicle stock"] * prm[
            "vehicle_glass_intensity"]
        stk["Vehicle stock"].inflow[...] = flw["sysenv => Vehicle stock"]
        stk["Vehicle stock"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Vehicle stock"].compute()
        stk["Steel stock in vehicles"].inflow[...] = flw["sysenv => Steel stock in vehicles"]
        stk["Steel stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Steel stock in vehicles"].compute()
        stk["Plastics stock in vehicles"].inflow[...] = flw["sysenv => Plastics stock in vehicles"]
        stk["Plastics stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Plastics stock in vehicles"].compute()
        stk["Glass stock in vehicles"].inflow[...] = flw["sysenv => Glass stock in vehicles"]
        stk["Glass stock in vehicles"].lifetime_model.set_prms(
            mean=prm["vehicle_lifetime_mean"], std=prm["vehicle_lifetime_std"]
        )
        stk["Glass stock in vehicles"].compute()
        flw["Steel stock in vehicles => sysenv"][...] = stk["Steel stock in vehicles"].outflow
        flw["Plastics stock in vehicles => sysenv"][...] = stk["Plastics stock in vehicles"].outflow
        flw["Glass stock in vehicles => sysenv"][...] = stk["Glass stock in vehicles"].outflow
