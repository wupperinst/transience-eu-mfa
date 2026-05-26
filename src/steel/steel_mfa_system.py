import flodym as fd
import numpy as np
import logging


class SteelMFASystem(fd.MFASystem):

    def compute(self):
        """
        Perform all computations for the MFA system in sequence.
        """
        self.interpolate_parameters()
        if self.cfg.customization.model_driven == 'production':
            self.compute_inflows_production_driven()
        elif self.cfg.customization.model_driven == 'final_demand':
            self.compute_inflows_final_demand_driven()
        elif self.cfg.customization.model_driven == 'final_demand_with_start_value_and_growth_rate':
            self.compute_inflows_final_demand_driven(with_start_value_and_growth_rate=True)
        else:
            raise ValueError(f"Config item model_driven has invalid value: {self.cfg.model_driven}. Choose 'production', 'final_demand', or 'final_demand_with_start_value_and_growth_rate'.")
        self.compute_stock()
        self.compute_outflows()


    def _prepare_interpolate(self, array): 
        try:
            xp=np.nonzero(array)[0].tolist()
            xp.sort()
            x=list(range(min(xp),max(xp)+1))
            return xp, x
        except ValueError:
            return None, None

    def interpolate_parameters(self):
        """
        Interpolate parameters to the model time step.
        """
        
        logging.info("mfa_system - interpolate_parameters")

        # Abbreviation for better readability
        prm = self.parameters
        Nr = len(self.dims["r"].items)
        Ns = len(self.dims["s"].items)
        Ni = len(self.dims["i"].items)
        Np = len(self.dims["p"].items)
        Nw = len(self.dims["w"].items)
        Ne = len(self.dims["e"].items)

        # DOMESTIC PRODUCTION, IMPORT NEW (absolute), EXPORT NEW (absolute)
        # Index: rtsipe
        # These data should already be provided for each year.

        # EoLRecoveryRate
        # Index: rtsip

        for param in ['NewScrapRate', 'EoLRecoveryRate']:

            logging.info('Interpolating parameter ' + param)
            for r in np.arange(0,Nr):
                for s in np.arange(0,Ns):
                    for i in np.arange(0,Ni):
                        for p in np.arange(0,Np):

                            xp,x = self._prepare_interpolate(prm[param].values[r,:,s,i,p])
                            if xp is not None:
                                fp = prm[param].values[r,xp,s,i,p]
                                yp = np.interp(x, xp, fp)
                                prm[param].values[r,x,s,i,p] = yp

        # Contamination
        # Index: rtsipe

        for param in ['Contamination']:

            logging.info('Interpolating parameter ' + param)
            for r in np.arange(0,Nr):
                for s in np.arange(0,Ns):
                    for i in np.arange(0,Ni):
                        for p in np.arange(0,Np):
                            for e in np.arange(0,Ne):

                                xp,x = self._prepare_interpolate(prm[param].values[r,:,s,i,p,e])
                                if xp is not None:
                                    fp = prm[param].values[r,xp,s,i,p,e]
                                    yp = np.interp(x, xp, fp)
                                    prm[param].values[r,x,s,i,p,e] = yp

        # ScrapSortingRate
        # Index: rtsipw

        for param in ['ScrapSortingRate']:

            logging.info('Interpolating parameter ' + param)
            for r in np.arange(0,Nr):
                for s in np.arange(0,Ns):
                    for i in np.arange(0,Ni):
                        for p in np.arange(0,Np):
                            for w in np.arange(0,Nw):

                                xp,x = self._prepare_interpolate(prm[param].values[r,:,s,i,p,w])
                                if xp is not None:
                                    fp = prm[param].values[r,xp,s,i,p,w]
                                    yp = np.interp(x, xp, fp)
                                    prm[param].values[r,x,s,i,p,w] = yp

        logging.info('Those parameters were not interpolated (i.e. must be provided in full):\n \
                        DomesticProduction, ImportNew, ExportNew, InitialStock')


    def compute_inflows_production_driven(self):
        """
        Compute flows from production downstream down to to final consumption entering the stock.
        """
        
        logging.info("mfa_system - compute_inflows_production_driven")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in steel_definition.py
        aux = {
        }

        ### STEEL PRODUCT MARKET
        logging.info("mfa_system - STEEL PRODUCT MARKET")

        # Initialise exogenously defined flows
        flw["sysenv => Steel product market"][...] = prm["DomesticProduction"] # F_0_1_Domestic
        flw["sysenv => IMPORT Steel product market"][...] = prm["ImportNewProducts"] # F_0_1_Import
        flw["Steel product market => sysenv"][...] = prm["ExportNewProducts"] # F_1_0
        # Endogenous output flow (mass balance equation)
        flw["Steel product market => Steel goods manufacturing"][...] = (
            flw["sysenv => Steel product market"][...] +
            flw["sysenv => IMPORT Steel product market"][...] -
            flw["Steel product market => sysenv"][...]
        )
        
        ### STEEL GOODS MANUFACTURING
        logging.info("mfa_system - STEEL GOODS MANUFACTURING")

        # Endogenous output flow (mass balance equation)
        flw["Steel goods manufacturing => sysenv"][...] = flw["Steel product market => Steel goods manufacturing"][...] * prm["NewScrapRate"] # F_2_0
        flw["Steel goods manufacturing => Steel goods market"][...] = (
            flw["Steel product market => Steel goods manufacturing"][...] -
            flw["Steel goods manufacturing => sysenv"][...]
        ) # F_2_3

        ### STEEL GOODS MARKET
        logging.info("mfa_system - STEEL GOODS MARKET")

        # Initialise exogenously defined flows
        flw["sysenv => Steel goods market"][...] = prm["ImportNewGoods"] # F_0_3_Import
        flw["Steel goods market => sysenv"][...] = prm["ExportNewGoods"] # F_3_0
        # Endogenous output flow (mass balance equation)
        flw["Steel goods market => End use stock"][...] = (
            flw["Steel goods manufacturing => Steel goods market"][...] +
            flw["sysenv => Steel goods market"][...] -
            flw["Steel goods market => sysenv"][...]
        ) # F_3_4


    def _extrapolate_parameter_start_value_and_growth_rate(self, start_value: fd.FlodymArray, growth_rate: fd.FlodymArray, dimensions: list) -> fd.FlodymArray:
            """
            Extrapolate a parameter based on its start value and growth rate.
            The parameter is assumed to be defined as:
            parameter[1] = start_value[0] * growth_rate[1]
            parameter[t+1] = parameter[t-1] * growth_rate[t]
            where start_value is the initial value at the beginning of the time series,
            and growth_rate is a multiplicative growth factor over time.

            WARNING: this function is *not* generic and only works for the specific case of FinalDemand extrapolation
            (or other parameters with same dimensions).
            """

            # parameter = self.get_new_array(dim_letters=("r","t","s","p","e"))

            # Identify the start year and max extrapolation year
            df_start_value = start_value.to_df(index=False)
            df_start_value = df_start_value.loc[df_start_value['value']!=0, :] # Only the start year has non-zero values
            df_start_value.rename(columns={'value': 'start_value'}, inplace=True)
            start_year = df_start_value['time'].iloc[0]
            
            df_growth_rate = growth_rate.to_df(index=False)
            df_growth_rate.rename(columns={'value': 'growth_rate'}, inplace=True)
            max_year = df_growth_rate['time'].max()

            # Extrapolate start_value with growth_rate over time
            df_combined = df_growth_rate.merge(df_start_value, on=dimensions, how='outer')
            df_combined['value'] = 0.0
            df_combined['growth_rate'] = 1 + df_combined['growth_rate']

            for year in range(start_year, max_year + 1):
                mask = (df_combined['time'] == year)
                if year == start_year:
                    df_combined.loc[mask, 'value'] = df_combined.loc[mask, 'start_value']
                else:
                    prev_year_mask = (df_combined['time'] == year - 1)
                    df_combined.loc[mask, 'value'] = df_combined.loc[prev_year_mask, 'value'].values * df_combined.loc[mask, 'growth_rate'].values

            all_dimensions = dimensions + ['value']
            df_combined = df_combined[all_dimensions]
            parameter = fd.FlodymArray.from_df(dims=start_value.dims, df=df_combined, allow_missing_values=True)

            return parameter


    def compute_inflows_final_demand_driven(self, with_start_value_and_growth_rate: bool =False):
        """
        Compute flows from final consumption entering the stock upstream to production.
        """
        
        if not with_start_value_and_growth_rate:
            logging.info("mfa_system - compute_inflows_final_demand_driven")
        else:
            logging.info("mfa_system - compute_inflows_final_demand_driven with start value and growth rate")
            

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in steel_definition.py
        aux = {
        }

        ### STEEL GOODS MARKET
        logging.info("mfa_system - STEEL GOODS MARKET")

        # Initialise exogenously defined flow
        if with_start_value_and_growth_rate:
            logging.info("Building FinalDemand from start_value and growth_rate parameters.")
            if "FinalDemand" not in prm:
                self.parameters["FinalDemand"] = self._extrapolate_parameter_start_value_and_growth_rate(
                     prm["start_value"], prm["growth_rate"], 
                     dimensions=["region", "time", "sector", "intermediate", "product", "element"]
                )
        else:
            logging.info("Using FinalDemand provided as exogenous parameter.")
        flw["Steel goods market => End use stock"][...] = prm["FinalDemand"] # F_3_4: New steel goods

        # Account for trade flows
        flw["sysenv => Steel goods market"][...] = prm["ImportNewGoods"] # F_0_3_Import
        flw["Steel goods market => sysenv"][...] = prm["ExportNewGoods"] # F_3_0
        # Endogenous input flow (mass balance equation)
        flw["Steel goods manufacturing => Steel goods market"][...] = (
            flw["Steel goods market => End use stock"][...] -
            flw["sysenv => Steel goods market"][...] +
            flw["Steel goods market => sysenv"][...]
        ) # F_2_3

        ### STEEL GOODS MANUFACTURING
        logging.info("mfa_system - STEEL GOODS MANUFACTURING")

        # Endogenous input flow (mass balance equation)
        flw["Steel product market => Steel goods manufacturing"][...] = (
            flw["Steel goods manufacturing => Steel goods market"][...] 
            / (1 - prm["NewScrapRate"])
        ) # F_1_2

        flw["Steel goods manufacturing => sysenv"][...] = (
            flw["Steel product market => Steel goods manufacturing"][...] 
            - flw["Steel product market => Steel goods manufacturing"][...]
        ) # F_2_0

        ### STEEL PRODUCT MARKET
        logging.info("mfa_system - STEEL PRODUCT MARKET")

        # Initialise exogenously defined flows
        flw["sysenv => IMPORT Steel product market"][...] = prm["ImportNewProducts"] # F_0_1_Import
        flw["Steel product market => sysenv"][...] = prm["ExportNewProducts"] # F_1_0
        # Endogenous input flow (mass balance equation)
        flw["sysenv => Steel product market"][...] = (
            flw["Steel product market => Steel goods manufacturing"][...] -
            flw["sysenv => IMPORT Steel product market"][...] +
            flw["Steel product market => sysenv"][...]
        ) # F_0_1_DomesticProduction


    def compute_stock(self):
        """
        Compute inflow-driven stock dynamics.
        """
        
        logging.info("mfa_system - compute_stock")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in steel_definition.py
        aux = {
        }

        ### END USE STOCK
        logging.info("mfa_system - END USE STOCK")

        stk["End use stock"].inflow[...] = flw["Steel goods market => End use stock"]
        stk["End use stock"].lifetime_model.set_prms(
            mean=self.parameters["Lifetime"],
            std=self.parameters["Lifetime"] * 0.3,
        )
        stk["End use stock"].compute()


    def compute_outflows(self):
        """
        Compute flows after leaving the stock.
        """
        
        logging.info("mfa_system - compute_outflows")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in steel_definition.py
        aux = {
            "EOLFlow": self.get_new_array(dim_letters=("t","c","r","s","i","p","e")),
            "ContaminatedScrap": self.get_new_array(dim_letters=("r", "t", "s", "i", "p", "e")),
            "ScrapLossRate": self.get_new_array(dim_letters=("r", "t", "s", "i", "p", "w")),
        }

        ### EOL STEEL
        logging.info("mfa_system - EOL STEEL")

        #aux["EOLFlow"].set_values(stk["End use stock"]._outflow_by_cohort)
        #flw["End use stock => Waste management"][...] = aux["EOLFlow"] * prm["EoLRecoveryRate"] # F_4_5: Collected end-of-life steel products
        
        flw["End use stock => Waste management"][...] = stk["End use stock"].outflow * prm["EoLRecoveryRate"] # F_4_5: Collected end-of-life steel products
        flw["End use stock => sysenv"][...] = stk["End use stock"].outflow * (1 - prm["EoLRecoveryRate"]) # F_4_0: Lost end-of-life steel products

        ### WASTE MANAGEMENT
        logging.info("mfa_system - WASTE MANAGEMENT")

        # Contamination
        # Sum recovered EoL flow over age cohorts
        #aux["ContaminatedScrap"][...] = flw["End use stock => Waste management"].sum_to(("r","t","s","i","p","e"))
        # The Cu content of the flow needs to be increased with the new contamination:
        # Total Cu contamination = Cu contamination in EoL flow + Contamination factor * EoL flow
        # Element Cu has index 1 in Element classification [All, Cu]        

        #aux["ContaminatedScrap"]["All"] += prm["Contamination"]["Cu"] * aux["ContaminatedScrap"]["All"]
        aux["ContaminatedScrap"]["All"] = (flw["End use stock => Waste management"] 
                                           + flw["End use stock => Waste management"] * prm["Contamination"]["Cu"])

        #aux["ContaminatedScrap"]["Cu"] += prm["Contamination"]["Cu"] * aux["ContaminatedScrap"]["All"]
        aux["ContaminatedScrap"]["Cu"] = flw["End use stock => Waste management"] * prm["Contamination"]["Cu"]

        # Sorting scrap
        flw["Waste management => AVAILABLE SCRAP sysenv"][...] = aux["ContaminatedScrap"] * prm["ScrapSortingRate"] # F_5_0_AvailableScrap
        aux["ScrapLossRate"][...] = 1 - prm["ScrapSortingRate"]
        flw["Waste management => LOST SCRAP sysenv"][...] = aux["ContaminatedScrap"] * aux["ScrapLossRate"] # F_5_0_LostScrap


    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}