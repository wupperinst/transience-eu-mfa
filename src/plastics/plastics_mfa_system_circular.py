import flodym as fd
import numpy as np
import logging


class CircularPlasticsMFASystem(fd.MFASystem):

    def compute(self):
        """
        Perform all computations for the MFA system in sequence.
        """
        if not self.cfg.customization.prodcom:
            self.interpolate_parameters()
        if self.cfg.customization.model_driven == 'production':
            self.compute_inflows_production_driven()
        elif self.cfg.customization.model_driven == 'final_demand':
            self.compute_circular_mfa()
        elif self.cfg.customization.model_driven == 'final_demand_with_start_value_and_growth_rate':
            self.compute_circular_mfa(with_start_value_and_growth_rate=True)
        else:
            raise ValueError(f"Config item model_driven has invalid value: {self.cfg.model_driven}. Choose 'production', 'final_demand', or 'final_demand_with_start_value_and_growth_rate'.")
        # self.compute_stock()
        # self.compute_outflows()


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
        Np = len(self.dims["p"].items)
        Nw = len(self.dims["w"].items)
        Nm = len(self.dims["m"].items)
        Nz = len(self.dims["z"].items)

        # DOMESTIC DEMAND, IMPORT NEW (absolute), EXPORT NEW (absolute)
        # Index: rtspe
        # These data should already be provided for each year.
        # Note that for import and export another variant is possible using import rates, and those are interpolated below.

        # ImportRateNew, ExportRateNew, MarketShare
        # Index: rrtsp

        for param in ['MarketShare']:#['ImportRateNew', 'ExportRateNew', 'MarketShare']:
            
            logging.info('Interpolating parameter ' + param)
            for r in np.arange(0,Nr):
                for rr in np.arange(0,Nr):
                    for s in np.arange(0,Ns):
                        for p in np.arange(0,Np):

                            xp,x = self._prepare_interpolate(prm[param].values[r,rr,:,s,p])                    
                            if xp is not None:
                                fp = prm[param].values[r,rr,xp,s,p]
                                yp = np.interp(x, xp, fp)
                                prm[param].values[r,rr,x,s,p] = yp

        # ImportUsed, ExportUsed, ImportRateUsed, ExportRateUsed
        # Index: rrtcsp

        # => Cannot be interpolated
                        
        # RecyclateShare, EoLCollectionRate, EoLUtilisationRate, DeprivedRate
        # Index: rtsp

        for param in ['RecyclateShare', 'EoLCollectionRate', 'EoLUtilisationRate', 'DeprivedRate', 
                      'ReuseRate', 'MaxReuseCycles', 'MaxMechanicalRecyclingCycles']:

            logging.info('Interpolating parameter ' + param)

            for r in np.arange(0,Nr):
                for s in np.arange(0,Ns):
                    for p in np.arange(0,Np):

                        xp,x = self._prepare_interpolate(prm[param].values[r,:,s,p])                    
                        if xp is not None:
                            fp = prm[param].values[r,xp,s,p]
                            yp = np.interp(x, xp, fp)
                            prm[param].values[r,x,s,p] = yp

        # SortingRate
        # Index: rtspw
        logging.info('Interpolating parameter SortingRate')
        for r in np.arange(0,Nr):
            for s in np.arange(0,Ns):
                for p in np.arange(0,Np):
                    for w in np.arange(0,Nw):

                        xp,x = self._prepare_interpolate(prm['SortingRate'].values[r,:,s,p,w])
                        if xp is not None:
                            fp = prm['SortingRate'].values[r,xp,s,p,w]
                            yp = np.interp(x, xp, fp)
                            prm['SortingRate'].values[r,x,s,p,w] = yp

        # ImportRateSorted, ExportRateSorted
        # index: rrtspw

        for param in ['ImportRateSortedWaste', 'ExportRateSortedWaste']:
            
            logging.info('Interpolating parameter ' + param)

            for r in np.arange(0,Nr):
                for rr in np.arange(0,Nr):
                    for s in np.arange(0,Ns):
                        for p in np.arange(0,Np):
                            for w in np.arange(0,Nw):

                                xp,x = self._prepare_interpolate(prm[param].values[r,rr,:,s,p,w])                    
                                if xp is not None:
                                    fp = prm[param].values[r,rr,xp,s,p,w]
                                    yp = np.interp(x, xp, fp)
                                    prm[param].values[r,rr,x,s,p,w] = yp
                            
        # RecyclingLossRate
        # Index: rtpw
        logging.info('Interpolating parameter RecyclingLossRate')
        for r in np.arange(0,Nr):
            for s in np.arange(0,Ns):
                for p in np.arange(0,Np):
                    for w in np.arange(0,Nw):
                        for m in np.arange(0,Nm):

                            xp,x = self._prepare_interpolate(prm['RecyclingConversionRate'].values[r,:,s,p,w,m])
                            if xp is not None:
                                fp = prm['RecyclingConversionRate'].values[r,xp,s,p,w,m]
                                yp = np.interp(x, xp, fp)
                                prm['RecyclingConversionRate'].values[r,x,s,p,w,m] = yp

        logging.info('Those parameters were not interpolated (i.e. must be provided in full):\n \
                        DomesticDemand, ImportNew, ExportNew, ImportUsed, ExportUsed, ImportRateUsed, ExportRateUsed')


    def _extrapolate_parameter_start_value_and_growth_rate(self, start_value: fd.FlodymArray, growth_rate: fd.FlodymArray):
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
        # Identify the start year and max extrapolation year
        df_start_value = start_value.to_df(index=False)
        df_start_value = df_start_value.loc[df_start_value['value']!=0, :] # Only the start year has non-zero values
        df_start_value.rename(columns={'value': 'start_value'}, inplace=True)
        start_year = df_start_value['time'].iloc[0]
        
        df_growth_rate = growth_rate.to_df(index=False)
        df_growth_rate.rename(columns={'value': 'growth_rate'}, inplace=True)
        max_year = df_growth_rate['time'].max()

        # Extrapolate start_value with growth_rate over time
        df_combined = df_growth_rate.merge(df_start_value, on=['region','time','sector','polymer','element'], how='outer')
        df_combined['value'] = 0.0
        df_combined['growth_rate'] = 1 + df_combined['growth_rate']

        for year in range(start_year, max_year + 1):
            mask = (df_combined['time'] == year)
            if year == start_year:
                df_combined.loc[mask, 'value'] = df_combined.loc[mask, 'start_value']
            else:
                prev_year_mask = (df_combined['time'] == year - 1)
                df_combined.loc[mask, 'value'] = df_combined.loc[prev_year_mask, 'value'].values * df_combined.loc[mask, 'growth_rate'].values

        df_combined = df_combined[['region','time','sector','polymer','element','value']]
        parameter = fd.FlodymArray.from_df(dims=start_value.dims, df=df_combined, allow_missing_values=True)

        return parameter


    def compute_circular_mfa(self, with_start_value_and_growth_rate: bool = False):
        """
        Compute the circular MFA of plastics, i.e. explicitely accounting for recycling loops and reuse cycles.
        """

        logging.info("mfa_system - compute_circular_mfa")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
            # Reuse
            "ReuseRate": self.get_new_array(dim_letters=("r", "t", "s", "p", "z")),
            # from final demand back to production
            "DomesticInputManufacturing": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x")),
            "ImportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ExportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "NetImport": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            # Stock
            "StockInflow": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x", "z")),
            # EOL plastics
            "CollectedWaste": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x", "z")),
            "UtilisedWaste": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x", "z")),
            "SortedWaste": self.get_new_array(dim_letters=("r", "t", "s", "p", "w", "e", "x", "z")),
            "SortedEOL_agg": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x", "z")),
            "SortedEOL_inclImports": self.get_new_array(dim_letters=("r", "t", "s", "p", "w", "e", "x", "z")),
            # Reuse
            "ReusedPlastics": self.get_new_array(dim_letters=("r", "t", "s", "p", "e", "x", "z")),
            # Recycling
            "RecyclingConversionRate": self.get_new_array(dim_letters=("r", "t", "s", "p", "w", "m", "x")),
            "PrimaryContent": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "RecycledContent": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
    }

        # TMP!!!
        time_step = 0.25

        Nr = len(self.dims["r"].items)
        Nt = len(self.dims["t"].items)
        Ns = len(self.dims["s"].items)
        Np = len(self.dims["p"].items)
        Ne = len(self.dims["e"].items)
        Nw = len(self.dims["w"].items)
        Nm = len(self.dims["m"].items)
        Nx = len(self.dims["x"].items)
        Nz = len(self.dims["z"].items)

        logging.info('Building ReuseRate parameter with MaxReuseCycles')
        for r in np.arange(0,Nr):
            for t in np.arange(0,Nt):
                for s in np.arange(0,Ns):
                    for p in np.arange(0,Np):

                        max_reuse_cycles = int(prm["MaxReuseCycles"].values[r,t,s,p])
                        for z in np.arange(0,Nz):
                            if z < max_reuse_cycles:
                                aux["ReuseRate"].values[r,t,s,p,z] = prm["ReuseRate"].values[r,t,s,p]
                            else:
                                aux["ReuseRate"].values[r,t,s,p,z] = 0.0

        logging.info('Building RecyclingConversionRate parameter with MaxMechanicalRecyclingCycles')
        for r in np.arange(0,Nr):
            for t in np.arange(0,Nt):
                for s in np.arange(0,Ns):
                    for p in np.arange(0,Np):

                        max_mechanical_recycling_cycles = int(prm["MaxMechanicalRecyclingCycles"].values[r,t,s,p])

                        for w in np.arange(0,Nw):
                            for m in np.arange(0,Nm):

                                for x in np.arange(0,Nx):
                                    if x < max_mechanical_recycling_cycles:
                                        aux["RecyclingConversionRate"].values[r,t,s,p,w,m,x] = prm["RecyclingConversionRate"].values[r,t,s,p,w,m]
                                    else:
                                        aux["RecyclingConversionRate"].values[r,t,s,p,w,m,x] = 0.0

###############################################################################################

        ### REUSE & RECYCLING CYCLES
        logging.info("mfa_system - REUSE & RECYCLING CYCLES")

        for t in self.dims["t"].items:
            logging.info(f"Computing CE for year {t}.")

        ### FINAL DEMAND

            if t == min(self.dims["t"].items): # i.e. first year of the model
                # Initial FinalDemand is assumed to be in first reuse cycle (i.e. not yet reused)
                # F_3_4_NewPlastics
                if with_start_value_and_growth_rate:
                    # Total final demand
                    if "FinalDemand" not in prm:
                        self.parameters["FinalDemand"] = self.get_new_array(dim_letters=("r","t","s","p","e"))
                        prm["FinalDemand"][{'t': t}] = prm["start_value"][{'t': t}]
                else:
                    #logging.info("Using FinalDemand provided as exogenous parameter.")
                    pass

                # In the first year, final demand is met entirely with new/recycled plastics, and there are no reused plastics from previous cycles yet.
                flw["Plastics market => End use stock"][{'t': t, 'x': 0, 'z': 0}] = prm["FinalDemand"][{'t': t}]
                flw["Reuse => End use stock"][{'t': t}] = 0

            else: # t > min_t
                # For subsequent years, the inflow to the stock is made of new plastics and reused plastics from previous cycles
                if with_start_value_and_growth_rate:
                    # Total final demand 
                    prm["FinalDemand"][{'t': t}] = prm["FinalDemand"][{'t': t - time_step}] * (1 + prm["growth_rate"][{'t': t}])
                else:
                    #logging.info("Using FinalDemand provided as exogenous parameter.")
                    pass

                # Final demand
                # Reused plastics, z>0
                # Increment cycle counter for reused plastics
                # Note: for x>MaxReuseCycles, the ReuseRate is set to 0, so "Waste collection => Reuse" is 0.
                #for z in range(len(self.dims["z"].items) - 1):
                for z in np.arange(0,Nz-1):
                    flw["Reuse => End use stock"][{'t': t, 'z': z+1}] = flw["Waste collection => Reuse"][{'t': t - time_step, 'z': z}]
                flw["Reuse => End use stock"][{'t': t, 'z': 0}] = 0


                # Mechanically recycled plastics x>0
                # Increment cycle counter for mechanically recycled plastics
                # Note: for x>MaxMechanicalRecyclingCycles, the RecyclingConversionRate is set to 0, so "Recycling => Polymer market" is 0.
                #for x in range(len(self.dims["x"].items) - 1):
                for x in np.arange(0,Nx-1):
                    flw["Recyclate market => Polymer market"][{'t': t, 'x': x+1}] = flw["Recycling => Recyclate market"][{'t': t - time_step, 'x': x}]
                flw["Recyclate market => Polymer market"][{'t': t, 'x': 0}] = 0

                # Final demand
                # Assumption: final demand and imports have the same rate of recycled content and the same cycle distribution as "Recycling => Polymer market".
                # Assumption: reused materials replace first use material in the same recycled cycle (i.e. same x).
                for r in self.dims["r"].items:
                    for s in self.dims["s"].items:
                        for p in self.dims["p"].items:
                            for e in self.dims["e"].items:

                                flw["Plastics market => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': 0, 'z': 0}] = (
                                    prm["FinalDemand"][{'r': r, 't': t, 's': s, 'p': p}] * (1 - prm["RecyclateShare"][{'r': r, 't': t, 's': s, 'p': p}]) 
                                    - flw["Reuse => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': 0}].sum_over(('z'))
                                )
                                # if flw["Plastics market => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': 0, 'z': 0}].values < 0:
                                #     flw["Plastics market => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': 0, 'z': 0}] = 0

                                for x in np.arange(1,Nx):
                                    if flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}].sum_over('x').values != 0:
                                        ShareCycle = flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': x}] / flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}].sum_over('x')
                                        flw["Plastics market => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': x, 'z': 0}] = (
                                            prm["FinalDemand"][{'r': r, 't': t, 's': s, 'p': p}] 
                                            * prm["RecyclateShare"][{'r': r, 't': t, 's': s, 'p': p}] 
                                            * ShareCycle 
                                            - flw["Reuse => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': x}].sum_over(('z'))
                                        )
                                    else:
                                        flw["Plastics market => End use stock"][{'r': r, 't': t, 's': s, 'p': p, 'e': e, 'x': x, 'z': 0}] = 0


###############################################################################################
            ### UPSTREAM FLOWS TO PRODUCTION (CONVERTER DEMAND) 
            # Compute flows from final consumption entering the stock upstream up to production (converter demand).

            # F_2_3_NewPlastics
            # Note: "Plastics market => End use stock" is indexed with "z" but only has z=0 for new plastics, so we eliminate this dimension here
            flw["Plastics manufacturing => Plastics market"].values = np.einsum('rtspexz,rRtsp->Rtspex',
                                                                            flw["Plastics market => End use stock"].values,
                                                                            prm["MarketShare"].values)

            ### PLASTICS MANUFACTURING
            #logging.info("mfa_system - PLASTICS MANUFACTURING")

            # Remove absolute import and export provided exogenously.
            # Note: not implementing rate of import and export as in production_driven.
            # Imports: absolute
            # flw["sysenv => Plastics manufacturing"][...] = prm["ImportNew"] # F_0_2_ImportNew
            # # Exports: absolute
            # flw["Plastics manufacturing => sysenv"][...] = prm["ExportNew"] # F_2_0_ExportNew

            # Sum over all import and export regions to calculate TOTAL imports and exports and NET imports
            # aux["ImportNew"][...] = flw["sysenv => Plastics manufacturing"].sum_to(("r","t","s","p","e"))
            # aux["ExportNew"][...] = flw["Plastics manufacturing => sysenv"].sum_to(("r","t","s","p","e"))
            # aux["NetImport"][...] = aux["ImportNew"] - aux["ExportNew"]

            ### POLYMER MARKET
            #logging.info("mfa_system - POLYMER MARKET")

            if t == min(self.dims["t"].items): # i.e. first year of the model

                #flw["Polymer market => PRIMARY Plastics manufacturing"][{'t': t, 'x': 0}] = flw["Plastics manufacturing => Plastics market"][{'t': t}].sum_over('x') + aux["NetImport"][{'t': t}] # F_1_2_Primary
                flw["Polymer market => PRIMARY Plastics manufacturing"][{'t': t, 'x': 0}] = flw["Plastics manufacturing => Plastics market"][{'t': t}].sum_over('x') # F_1_2_Primary
                flw["Polymer market => SECONDARY Plastics manufacturing"][{'t': t}] = 0 # F_1_2_Recyclate

            else: # t > min_t

                # Primary vs. recycled content in plastics put to market
                aux["PrimaryContent"][{'t': t}] = flw["Plastics manufacturing => Plastics market"][{'t': t, 'x': 0}]
                aux["RecycledContent"][{'t': t}] = flw["Plastics manufacturing => Plastics market"][{'t': t}].sum_over('x') - aux["PrimaryContent"][{'t': t}]

                # # Assumption: net imports have the same recycled content and cycle distribution as domestic plastics.
                # ShareCycle = {}
                # for x in np.arange(0,Nx):
                #     ShareCycle['x'] = flw["Plastics manufacturing => Plastics market"][{'t': t, 'x': x}] / flw["Plastics manufacturing => Plastics market"][{'t': t}].sum_over('x')

                # Primary polymers cover the converter demand not required to be met with recycled content
                flw["Polymer market => PRIMARY Plastics manufacturing"][{'t': t, 'x': 0}] = aux["PrimaryContent"][{'t': t}]
                #flw["Polymer market => PRIMARY Plastics manufacturing"][{'t': t, 'x': 0}] = aux["PrimaryContent"][{'t': t}] - aux["NetImport"][{'t': t}] * (1 - prm["RecyclateShare"][{'t': t}])

                for r in self.dims["r"].items:
                    for s in self.dims["s"].items:
                        for p in self.dims["p"].items:
                            for e in self.dims["e"].items:
                                                                
                                # RatioRecycledToRecyclate > 1
                                # means recycled content quotas exceed secondary production capacity 
                                # thus all mechanically recycled plastics are used domestically and the remaining demand for recycled content is imported ("Polymer market => RECYCLATE sysenv" < 0)
                                
                                # RatioRecycledToRecyclate < 1
                                # means recycled content quotas can be met with domestic mechanically recycled plastics, 
                                # and the excess mechanically recycled plastics are exported ("Polymer market => RECYCLATE sysenv" > 0)
                                
                                if flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}].sum_over('x').values != 0:
                                    RatioRecycledToRecyclate = aux["RecycledContent"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}] / flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}].sum_over('x')
                                else:
                                    RatioRecycledToRecyclate = 0
                                flw["Polymer market => SECONDARY Plastics manufacturing"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}] = flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}] * RatioRecycledToRecyclate
                                flw["Polymer market => RECYCLATE sysenv"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}] = flw["Recyclate market => Polymer market"][{'r': r, 't': t, 's': s, 'p': p, 'e': e}] * (1 - RatioRecycledToRecyclate)

###############################################################################################

            ### END USE STOCK
            #logging.info("mfa_system - END USE STOCK")

            aux["StockInflow"][...] = flw["Plastics market => End use stock"][...] + flw["Reuse => End use stock"][...]
            
            stk["End use stock"].inflow[...] = aux["StockInflow"]
            stk["End use stock"].lifetime_model.set_prms(
                mean=self.parameters["Lifetime"],
                #std=self.parameters["Lifetime"] * 0.3,
            )
            stk["End use stock"].compute()

###############################################################################################

            ### EOL PLASTICS
            #logging.info("mfa_system - EOL PLASTICS")

            #flw["End use stock => Waste collection"].set_values(stk["End use stock"]._outflow_by_cohort)
            flw["End use stock => Waste collection"][...] = stk["End use stock"].outflow
            
            ### WASTE COLLECTION & UTILISATION
            #logging.info("mfa_system - WASTE COLLECTION & UTILISATION")

            aux["CollectedWaste"][...] = flw["End use stock => Waste collection"] * prm["EoLCollectionRate"]
            aux["UtilisedWaste"][...] = aux["CollectedWaste"] * prm["EoLUtilisationRate"]

            #flw["Waste collection => LITTERING sysenv"][...] = (flw["End use stock => Waste collection"] - aux["CollectedWaste"])
            #flw["Waste collection => DEFAULT TREATMENT sysenv"][...] = (aux["CollectedWaste"] - aux["UtilisedWaste"])

            flw["Waste collection => Reuse"][{'t': t}] = aux["UtilisedWaste"][{'t': t}] * aux["ReuseRate"][{'t': t}]
            aux["ReusedPlastics"][{'t': t}] = aux["UtilisedWaste"][{'t': t}] * aux["ReuseRate"][{'t': t}] # incl. "c" dimension for subtracting from collected waste
            flw["Waste collection => Waste sorting"][{'t': t}] = aux["UtilisedWaste"][{'t': t}] - aux["ReusedPlastics"][{'t': t}]

            ### WASTE SORTING
            #logging.info("mfa_system - WASTE SORTING")

            aux["SortedWaste"][...] = flw["Waste collection => Waste sorting"] * prm["SortingRate"]

            flw["Waste sorting => Sorted waste market"].set_values(aux["SortedWaste"].values.copy())
            flw["Waste sorting => sysenv"].set_values(aux["SortedWaste"].values.copy())

            #waste_categories = self.dims.get_subset("w").dim_list[0].items
            waste_categories = self.dims["w"].items
            if self.cfg.customization.waste_not_for_recycling:
                try:
                    waste_not_for_recycling_ix = [waste_categories.index(k) for k in self.cfg.customization.waste_not_for_recycling]
                    waste_for_recycling = set(waste_categories) - set(self.cfg.customization.waste_not_for_recycling)
                except ValueError:
                    print('\nERROR: config Waste_Types_Not_For_Recycling does not match defined Classification Plastic_waste\n')
                    raise
            else:
                waste_not_for_recycling_ix = []
                #logging.warning('config: waste_not_for_recycling is empty! We assume all waste types are for recycling.')
            
            for w in np.arange(0, len(waste_categories)):
                if w in waste_not_for_recycling_ix:
                    flw["Waste sorting => Sorted waste market"].values[:,:,:,:,:,w,:,:] = 0
                else:
                    flw["Waste sorting => sysenv"].values[:,:,:,:,:,w,:,:] = 0


            ### SORTED WASTE MARKET
            #logging.info("mfa_system - SORTED WASTE MARKET")

            # # Import of sorted waste as import RATE
            # # ImportRateSortedWaste gives which waste categories are imported (as a % of total SortedEOL)
            # # Sum all age-cohorts and waste categories
            dim_letters_wo_waste = ("r","t","s","p","e","x")
            dim_letters_waste = ("r","t","s","p","w","e","x")

            # aux["SortedEOL_agg"] = flw["Waste sorting => Sorted waste market"].sum_to(dim_letters_wo_waste)
            # flw["sysenv => Sorted waste market"][...] = aux["SortedEOL_agg"] * prm["ImportRateSortedWaste"]
            # aux["SortedEOL_inclImports"][...] = (flw["Waste sorting => Sorted waste market"].sum_to(dim_letters_waste)
            #                                         + flw["sysenv => Sorted waste market"].sum_to(dim_letters_waste))
            # # Export of sorted waste as export RATE
            # # ExportRateSortedWaste gives which waste categories are exported (as a % of total SortedEOL_inclImports)
            # flw["Sorted waste market => sysenv"][...] = aux["SortedEOL_inclImports"] * prm["ExportRateSortedWaste"]

            # Net domestic input of sorted waste into recycling
            # flw["Sorted waste market => Recycling"][...] = aux["SortedEOL_inclImports"] - flw["Sorted waste market => sysenv"].sum_to(dim_letters_waste)
            flw["Sorted waste market => Recycling"][...] = flw["Waste sorting => Sorted waste market"].sum_over("z")

###############################################################################################

            ### RECYCLING
            #logging.info("mfa_system - RECYCLING")

            # Recycled plastics
            flw["Recycling => NON-MECH sysenv"][...] = flw["Sorted waste market => Recycling"] * aux["RecyclingConversionRate"]
            # Losses
            flw["Recycling => LOSSES sysenv"][...] = (flw["Sorted waste market => Recycling"].sum_to(dim_letters_wo_waste) 
                                                        - flw["Recycling => NON-MECH sysenv"].sum_to(dim_letters_wo_waste))
            # Mechanical recycling
            w_type = "Mechanical recycling"
            m_type = "Granulate"
            flw["Recycling => Recyclate market"][...] = flw["Recycling => NON-MECH sysenv"][{'m': m_type}]
            flw["Recycling => NON-MECH sysenv"][{'m': m_type}] = 0 # To respect mass balance, as mech. recycled polymers are sent back to "Polymer market"


###############################################################################################
###############################################################################################

    def get_flows_as_dataframes(self, flow_names=[]):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        if not flow_names:
            flow_names = list(self.flows.keys())
        dfs = {flow_name: self.flows[flow_name].to_df(sparse=True) for flow_name in flow_names}
        dfs_index_reset = {flow_name: df.reset_index() for flow_name, df in dfs.items()}
        return dfs_index_reset

    def aggregate_flows_by_age_cohort(self, flows_dfs, flow_names=[]):
        """Aggregate flow DataFrames by age-cohort."""
        if flow_names:
            flows_dfs = {flow_name: df for flow_name, df in flows_dfs.items() if flow_name in flow_names}
        for flow_name, df in flows_dfs.items():
            if 'age-cohort' in df.columns:
                logging.debug(f"Aggregating {flow_name}.")
                group_cols = [c for c in df.columns if (c != 'age-cohort' and c != 'value')]
                grouped = df.groupby(group_cols, as_index=False, sort=False).sum()
                df_agg = grouped.get(group_cols + ['value'])
                flows_dfs[flow_name] = df_agg
                logging.debug(df_agg.columns)
        return flows_dfs