import numpy as np
import flodym as fd


# floor area responds to service-sector output at 30% of its rate
FLOOR_AREA_ELASTICITY = 0.3

OLD_COHORTS = (">1945", "1945-1969", "1970-1989", "1990-2010", "2011-2020")
# new construction cohorts: (label, first year of period, last year of period)
NEW_COHORTS = (("2021-2030", 2021, 2030), ("2031-2040", 2031, 2040), ("2040<", 2041, 2050))


def _ordered(array, letters):
    """Return an array's values transposed into the given dim-letter order."""
    order = [array.dims.letters.index(letter) for letter in letters]
    return np.transpose(array.values, order)


def _assign(target, values, letters):
    """Write values, given in `letters` order, into a flodym array."""
    order = [letters.index(letter) for letter in target.dims.letters]
    target.values[...] = np.transpose(values, order)


class BuildingsMFASystem(fd.MFASystem):

    def compute(self):
        self.compute_building_stock()
        self.compute_flows()
        self.compute_stocks()

    # ----------------------------------------------------------------- #
    # the floor-area layer
    # ----------------------------------------------------------------- #
    def compute_building_stock(self):
        """
        Build the floor-area stock by age cohort, and the construction and
        demolition flows that follow from it.

        Residential floor area is driven by population, floor space per capita
        and the building share. Commercial floor area grows from its base-year
        level with service-sector output, damped by an elasticity. Both are then
        compared against the old stock: where the requirement exceeds the stock
        still standing, the difference is built; where it falls below, nothing is
        built and what already exists is retained, so the region carries a
        surplus rather than un-building itself.
        """
        prm = self.parameters
        stock = self.stocks["Building stock"]
        cohorts = list(stock.stock.dims["a"].items)
        years = list(stock.stock.dims["t"].items)

        # --- required stock (t, r, b) ---------------------------------------
        pop = _ordered(prm["building_population"], ("t", "r"))
        space = _ordered(prm["building_floor_space_per_capita"], ("t", "r"))
        share = _ordered(prm["building_residential_share"], ("t", "r", "b"))
        required = pop[:, :, None] * space[:, :, None] * share

        # commercial types carry a zero residential share, residential types a
        # zero base year, so the two halves simply add up
        service = _ordered(prm["building_service_output"], ("t", "r", "b"))
        base_year = _ordered(prm["building_commercial_base_year"], ("r", "b"))
        previous = np.where(service[:-1] == 0.0, np.nan, service[:-1])
        change = np.zeros_like(service)
        change[1:] = np.nan_to_num(service[1:] / previous - 1.0)
        factor = 1.0 + FLOOR_AREA_ELASTICITY * change
        factor[0] = 1.0
        required = required + base_year[None, :, :] * np.cumprod(factor, axis=0)

        # --- new construction ------------------------------------------------
        old = _ordered(prm["building_old_stock"], ("t", "r", "b", "a"))
        shortfall = required - old.sum(axis=3)
        # floored at zero and retained at its highest value: nothing is built
        # when the requirement falls, and nothing already built is un-built
        new_total = np.maximum.accumulate(np.clip(shortfall, 0.0, None), axis=0)

        # --- allocate the new stock to its construction period ---------------
        values = old.copy()
        for label, first, last in NEW_COHORTS:
            if label not in cohorts:
                continue
            j = cohorts.index(label)
            opened = years.index(first) - 1
            closes = years.index(last) if last in years else len(years) - 1
            for i, year in enumerate(years):
                if year < first:
                    continue
                values[i, :, :, j] = new_total[min(i, closes)] - new_total[opened]
        _assign(stock.stock, values, ("t", "r", "b", "a"))

        # --- construction and demolition -------------------------------------
        # A pre-2020 cohort can only shrink and a post-2020 cohort only grow, so
        # each yearly change belongs to exactly one of the two flows.
        change_by_cohort = np.zeros_like(values)
        change_by_cohort[1:] = values[1:] - values[:-1]
        is_old = np.array([cohort in OLD_COHORTS for cohort in cohorts])
        built = np.where(is_old, 0.0, np.clip(change_by_cohort, 0.0, None))
        demolished = np.where(is_old, np.clip(-change_by_cohort, 0.0, None), 0.0)
        _assign(stock.inflow, built, ("t", "r", "b", "a"))
        _assign(stock.outflow, demolished, ("t", "r", "b", "a"))
        # note: stock.compute() is deliberately not called -- it would overwrite
        # the stock with cumsum(inflow - outflow), which starts from zero and so
        # would drop the entire stock standing in the calibration year.

    # ----------------------------------------------------------------- #
    # the material layer
    # ----------------------------------------------------------------- #
    def compute_flows(self):
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        building_inflow = stk["Building stock"].inflow
        building_outflow = stk["Building stock"].outflow

        flw["sysenv => Steel stock in buildings"][...] = building_inflow * prm["building_steel_intensity"]
        flw["sysenv => Concrete stock in buildings"][...] = building_inflow * prm[
            "building_concrete_intensity"]
        flw["sysenv => Insulation stock in buildings"][...] = building_inflow * prm[
            "building_insulation_intensity"]
        flw["sysenv => Glass stock in buildings"][...] = building_inflow * prm["building_glass_intensity"]
        flw["Steel stock in buildings => sysenv"][...] = building_outflow * prm["building_steel_intensity"]
        flw["Concrete stock in buildings => sysenv"][...] = building_outflow * prm[
            "building_concrete_intensity"]
        flw["Insulation stock in buildings => sysenv"][...] = building_outflow * prm[
            "building_insulation_intensity"]
        flw["Glass stock in buildings => sysenv"][...] = building_outflow * prm[
            "building_glass_intensity"]

        # the reused fraction of the demolition stream re-enters the stock, so it
        # is subtracted from both primary demand and waste
        flw["Steel stock in buildings => Steel stock in buildings"][...] = \
            flw["Steel stock in buildings => sysenv"] * prm["building_steel_element_reuse"]
        flw["sysenv => Steel stock in buildings"][...] = \
            flw["sysenv => Steel stock in buildings"] - \
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Steel stock in buildings => sysenv"][...] = \
            flw["Steel stock in buildings => sysenv"] - \
            flw["Steel stock in buildings => Steel stock in buildings"]
        flw["Concrete stock in buildings => Concrete stock in buildings"][...] = \
            flw["Concrete stock in buildings => sysenv"] * prm["building_concrete_element_reuse"]
        flw["sysenv => Concrete stock in buildings"][...] = \
            flw["sysenv => Concrete stock in buildings"] - \
            flw["Concrete stock in buildings => Concrete stock in buildings"]
        flw["Concrete stock in buildings => sysenv"][...] = \
            flw["Concrete stock in buildings => sysenv"] - \
            flw["Concrete stock in buildings => Concrete stock in buildings"]

    def compute_stocks(self):
        """
        Material stocks, obtained by transforming the floor-area stock with the
        material intensities.

        This is the stock-level counterpart of the flow transformation, and it
        carries the material sitting in buildings that already stood in the
        calibration year -- which accumulating the flows from zero would miss.
        """
        prm = self.parameters
        building_stock = self.stocks["Building stock"].stock
        for material, intensity in (
            ("Steel", "building_steel_intensity"),
            ("Concrete", "building_concrete_intensity"),
            ("Insulation", "building_insulation_intensity"),
            ("Glass", "building_glass_intensity"),
        ):
            stock = self.stocks[f"{material} stock in buildings"]
            stock.stock[...] = (building_stock * prm[intensity]).sum_over(("b", "a"))
            stock.inflow[...] = self.flows[f"sysenv => {material} stock in buildings"]
            stock.outflow[...] = self.flows[
                f"{material} stock in buildings => sysenv"].sum_over(("a",))

    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}
