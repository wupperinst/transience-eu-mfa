import flodym as fd
import numpy as np
import logging


class PlasticsMFASystem(fd.MFASystem):

    def compute(self):
        """
        Perform all computations for the MFA system in sequence.
        """
        self.interpolate_parameters()
        if self.cfg.customization.model_driven == 'production':
            self.compute_inflows_production_driven()
        elif self.cfg.customization.model_driven == 'final_demand':
            self.compute_inflows_final_demand_driven()
        else:
            raise ValueError(f"Config item model_driven has invalid value: {self.cfg.model_driven}. Choose 'production' or 'final_demand'.")
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
        Np = len(self.dims["p"].items)
        Nw = len(self.dims["w"].items)
        Nm = len(self.dims["m"].items)

        # DOMESTIC DEMAND, IMPORT NEW (absolute), EXPORT NEW (absolute)
        # Index: rtspe
        # These data should already be provided for each year.
        # Note that for import and export another variant is possible using import rates, and those are interpolated below.

        # ImportRateNew, ExportRateNew, MarketShare
        # Index: rrtsp

        for param in ['ImportRateNew', 'ExportRateNew', 'MarketShare']:
            
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

        for param in ['RecyclateShare', 'EoLCollectionRate', 'EoLUtilisationRate', 'DeprivedRate']:

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


    def compute_inflows_production_driven(self):
        """
        Compute flows from production (converter demand) downstream down to final consumption entering the stock.
        """
        
        logging.info("mfa_system - compute_inflows_production_driven")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
            "DomesticInputManufacturing": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ImportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ExportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "NetImport": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
        }

        ### POLYMER MARKET
        logging.info("mfa_system - POLYMER MARKET")

        logging.debug(f"prm['DomesticDemand'].shape: {prm['DomesticDemand'].shape}")
        logging.debug(f"flw['sysenv => Polymer market'].shape: {flw['sysenv => Polymer market'].shape}")
        flw["sysenv => Polymer market"][...] = prm["DomesticDemand"] # F_0_1_Domestic
        
        logging.debug(f"prm['RecyclateShare'].shape: {prm['RecyclateShare'].shape}")
        logging.debug(f"flw['Polymer market => SECONDARY Plastics manufacturing'].shape: {flw['Polymer market => SECONDARY Plastics manufacturing'].shape}")
        logging.debug(f"flw['Polymer market => PRIMARY Plastics manufacturing'].shape: {flw['Polymer market => PRIMARY Plastics manufacturing'].shape}")
        flw["Polymer market => SECONDARY Plastics manufacturing"][...] = flw["sysenv => Polymer market"] * prm["RecyclateShare"] # F_1_2_Recyclate
        flw["Polymer market => PRIMARY Plastics manufacturing"][...] = flw["sysenv => Polymer market"] - flw["Polymer market => SECONDARY Plastics manufacturing"] # F_1_2_Primary

        ### PLASTICS MANUFACTURING
        logging.info("mfa_system - PLASTICS MANUFACTURING")

        # 1) Calculate import and export using rates applying to total domestic inputs to manufacturing
        # 2) Add absolute import and export provided exogenously
        # Note: 1) or 2) can be zero if the user only wants to use rates or absolute values.

        # Domestic input to manufacturing (primary + secondary)
        aux["DomesticInputManufacturing"] = flw["Polymer market => PRIMARY Plastics manufacturing"] + flw["Polymer market => SECONDARY Plastics manufacturing"] # InputManufacturing_1_2
        # Imports: absolute and via rates
        flw["sysenv => Plastics manufacturing"][...] = prm["ImportNew"] + aux["DomesticInputManufacturing"] * prm["ImportRateNew"] # F_0_2_ImportNew
        # Exports: absolute and via rates
        flw["Plastics manufacturing => sysenv"][...] = aux["DomesticInputManufacturing"] * prm["ExportRateNew"] + prm["ExportNew"] # F_2_0_ExportNew
        # Sum over all import and export regions to calculate TOTAL imports and exports and NET imports
        # ImportNew_0_2 = np.einsum('Rrtspe->rtspe', Plastics_MFA_System.FlowDict['F_0_2_ImportNew'].Values)
        # ExportNew_2_0 = np.einsum('rRtspe->rtspe', Plastics_MFA_System.FlowDict['F_2_0_ExportNew'].Values)
        aux["ImportNew"] = flw["sysenv => Plastics manufacturing"].sum_to(("r","t","s","p","e"))
        aux["ExportNew"] = flw["Plastics manufacturing => sysenv"].sum_to(("r","t","s","p","e"))
        aux["NetImport"] = aux["ImportNew"] - aux["ExportNew"]
        # Mass balance equation for plastics manufacturing
        flw["Plastics manufacturing => Plastics market"][...] = aux["DomesticInputManufacturing"] + aux["NetImport"] # F_2_3_NewPlastics

        ### PLASTICS MARKET
        logging.info("mfa_system - PLASTICS MARKET")

        # F_3_4_NewPlastics
        flw["Plastics market => End use stock"].values = np.einsum('rtspe,rRtsp->Rtspe',
                                                            flw["Plastics manufacturing => Plastics market"].values,
                                                            prm["MarketShare"].values)


    def compute_inflows_final_demand_driven(self):
        """
        Compute flows from final consumption entering the stock upstream up to production (converter demand).
        """

        logging.info("mfa_system - compute_inflows_final_demand_driven")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
            "DomesticInputManufacturing": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ImportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ExportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "NetImport": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
        }

        ### PLASTICS MARKET
        logging.info("mfa_system - PLASTICS MARKET")

        # F_3_4_NewPlastics
        flw["Plastics market => End use stock"][...] = prm["FinalDemand"]
        # F_2_3_NewPlastics
        flw["Plastics manufacturing => Plastics market"].values = np.einsum('rtspe,rRtsp->Rtspe',
                                                                        flw["Plastics market => End use stock"].values,
                                                                        prm["MarketShare"].values)

        ### PLASTICS MANUFACTURING
        logging.info("mfa_system - PLASTICS MANUFACTURING")

        # Remove absolute import and export provided exogenously.
        # Note: not implementing rate of import and export as in production_driven.
        # Imports: absolute
        flw["sysenv => Plastics manufacturing"][...] = prm["ImportNew"] # F_0_2_ImportNew
        # Exports: absolute
        flw["Plastics manufacturing => sysenv"][...] = prm["ExportNew"] # F_2_0_ExportNew

        # Sum over all import and export regions to calculate TOTAL imports and exports and NET imports
        aux["ImportNew"] = flw["sysenv => Plastics manufacturing"].sum_to(("r","t","s","p","e"))
        aux["ExportNew"] = flw["Plastics manufacturing => sysenv"].sum_to(("r","t","s","p","e"))
        aux["NetImport"] = aux["ImportNew"] - aux["ExportNew"]

        # Mass balance equation for plastics manufacturing
        aux["DomesticInputManufacturing"][...] = flw["Plastics manufacturing => Plastics market"][...] - aux["NetImport"] # F_2_3_NewPlastics

        ### POLYMER MARKET
        logging.info("mfa_system - POLYMER MARKET")

        # Use 1 - RecyclateShare to avoid "divide by zero" when splittig DomesticInputManufacturing into primary and secondary
        flw["Polymer market => PRIMARY Plastics manufacturing"][...] = aux["DomesticInputManufacturing"] / (1 - prm["RecyclateShare"]) # F_1_2_Primary
        flw["Polymer market => SECONDARY Plastics manufacturing"][...] = aux["DomesticInputManufacturing"] - flw["Polymer market => PRIMARY Plastics manufacturing"] # F_1_2_Recyclate

        flw["sysenv => Polymer market"][...] = aux["DomesticInputManufacturing"] # F_0_1_Domestic
        

    def compute_stock(self):
        """
        Compute inflow-driven stock dynamics.
        """
        
        logging.info("mfa_system - compute_stock")

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stocks

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
        }

        ### END USE STOCK
        logging.info("mfa_system - END USE STOCK")

        stk["End use stock"].inflow[...] = flw["Plastics market => End use stock"]
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

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
            "DeprivedEOL": self.get_new_array(dim_letters=("t", "c", "r", "s", "p", "e")),
            "CollectedWaste": self.get_new_array(dim_letters=("r", "t", "c", "s", "p", "e")),
            "UtilisedWaste": self.get_new_array(dim_letters=("r", "t", "c", "s", "p", "e")),
            "SortedWaste": self.get_new_array(dim_letters=("r", "t", "c", "s", "p", "w", "e")),
            "SortedEOL_agg": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "SortedEOL_inclImports": self.get_new_array(dim_letters=("r", "t", "s", "p", "w", "e")),
        }

        ### EOL PLASTICS
        logging.info("mfa_system - EOL PLASTICS")

        #flw["End use stock => Waste collection"].values = stk["End use stock"]._outflow_by_cohort
        flw["End use stock => Waste collection"].set_values(stk["End use stock"]._outflow_by_cohort)

        ### DEPRIVED VOLUMES
        logging.info("mfa_system - DEPRIVED VOLUMES")

        # DeprivedRate = Share of total generated waste (according to stock dynamics modelling) that is not actually reachable in reality.
        aux["DeprivedEOL"][...] = flw["End use stock => Waste collection"] * prm["DeprivedRate"]
        flw["End use stock => Waste collection"][...] = flw["End use stock => Waste collection"] - aux["DeprivedEOL"]
        # The deprived volumes are inserted back into the stock
        logging.debug(f"stk['End use stock']._stock_by_cohort.shape: {stk['End use stock']._stock_by_cohort.shape}")
        logging.debug(f"aux['DeprivedEOL'].shape: {aux['DeprivedEOL'].shape}")
        stk["End use stock"].stock[...] = stk["End use stock"].stock + aux["DeprivedEOL"]
        # The following lines are not syntactically correct in flodym:
        #stk["End use stock"].stock.set_values(stk["End use stock"].stock.values + aux["DeprivedEOL"])
        #stk["End use stock"].stock.values[...] = stk["End use stock"].stock.values + aux["DeprivedEOL"]
        # The following line is how it was done in ODYM
        #Plastics_MFA_System.StockDict['S_4'].Values = (Plastics_MFA_System.StockDict['S_4'].Values + Deprived_F_4_5)

        ### WASTE COLLECTION & UTILISATION
        logging.info("mfa_system - WASTE COLLECTION & UTILISATION")

        aux["CollectedWaste"][...] = flw["End use stock => Waste collection"] * prm["EoLCollectionRate"]
        aux["UtilisedWaste"][...] = aux["CollectedWaste"] * prm["EoLUtilisationRate"]
        flw["Waste collection => Waste sorting"][...] = aux["UtilisedWaste"]
        flw["Waste collection => LITTERING sysenv"][...] = (flw["End use stock => Waste collection"] - aux["CollectedWaste"])
        flw["Waste collection => DEFAULT TREATMENT sysenv"][...] = (aux["CollectedWaste"] - aux["UtilisedWaste"])

        ### WASTE SORTING
        logging.info("mfa_system - WASTE SORTING")

        logging.debug(f"flw['Waste collection => Waste sorting'].shape: {flw['Waste collection => Waste sorting'].shape}")
        logging.debug(f"prm['SortingRate'].shape: {prm['SortingRate'].shape}")
        logging.debug(f"aux['SortedWaste'].shape: {aux['SortedWaste'].shape}")
        
        aux["SortedWaste"][...] = flw["Waste collection => Waste sorting"] * prm["SortingRate"]
        logging.debug(f"aux['SortedWaste'].shape: {aux['SortedWaste'].shape}")

        flw["Waste sorting => Sorted waste market"].set_values(aux["SortedWaste"].values)
        flw["Waste sorting => sysenv"].set_values(aux["SortedWaste"].values)

        #waste_categories = self.dims.get_subset("w").dim_list[0].items
        waste_categories = self.dims["w"].items
        if self.cfg.customization.waste_not_for_recycling:
            try:
                waste_not_for_recycling_ix = [waste_categories.index(k) for k in self.cfg.customization.waste_not_for_recycling]
                logging.debug(f"Waste types NOT for recycling: {str(self.cfg.customization.waste_not_for_recycling)}")
                waste_for_recycling = set(waste_categories) - set(self.cfg.customization.waste_not_for_recycling)
                logging.debug(f"Waste types FOR recycling: {str(waste_for_recycling)}")
            except ValueError:
                print('\nERROR: config Waste_Types_Not_For_Recycling does not match defined Classification Plastic_waste\n')
                raise
        else:
            waste_not_for_recycling_ix = []
            logging.warning('config: waste_not_for_recycling is empty! We assume all waste types are for recycling.')
        
        for w in np.arange(0, len(waste_categories)):
            if w in waste_not_for_recycling_ix:
                flw["Waste sorting => Sorted waste market"].values[:,:,:,:,:,w,:] = 0
            else:
                flw["Waste sorting => sysenv"].values[:,:,:,:,:,w,:] = 0


        ### SORTED WASTE MARKET
        logging.info("mfa_system - SORTED WASTE MARKET")

        # Import of sorted waste as import RATE
        # ImportRateSortedWaste gives which waste categories are imported (as a % of total SortedEOL)
        # Sum all age-cohorts and waste categories
        aux["SortedEOL_agg"] = flw["Waste sorting => Sorted waste market"].sum_to(("r","t","s","p","e"))
        flw["sysenv => Sorted waste market"][...] = aux["SortedEOL_agg"] * prm["ImportRateSortedWaste"]
        aux["SortedEOL_inclImports"][...] = (flw["Waste sorting => Sorted waste market"].sum_to(("r","t","s","p","w","e"))
                                                + flw["sysenv => Sorted waste market"].sum_to(("r","t","s","p","w","e")))
        # Export of sorted waste as export RATE
        # ExportRateSortedWaste gives which waste categories are exported (as a % of total SortedEOL_inclImports)
        flw["Sorted waste market => sysenv"][...] = aux["SortedEOL_inclImports"] * prm["ExportRateSortedWaste"]

        # Net domestic input of sorted waste into recycling
        flw["Sorted waste market => Recycling"][...] = aux["SortedEOL_inclImports"] - flw["Sorted waste market => sysenv"].sum_to(("r","t","s","p","w","e"))


        ### RECYCLING
        logging.info("mfa_system - RECYCLING")

        # Recyclates
        flw["Recycling => RECYCLATE sysenv"][...] = flw["Sorted waste market => Recycling"] * prm["RecyclingConversionRate"]
        # Losses
        flw["Recycling => LOSSES sysenv"][...] = (flw["Sorted waste market => Recycling"].sum_to(("r","t","s","p","e")) 
                                                    - flw["Recycling => RECYCLATE sysenv"].sum_to(("r","t","s","p","e")))
        

    def get_flows_as_dataframes(self, flow_names=[]):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        if not flow_names:
            flow_names = list(self.flows.keys())
        return {flow_name: self.flows[flow_name].to_df() for flow_name in flow_names}