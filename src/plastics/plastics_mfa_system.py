import flodym as fd


class PlasticsMFASystem(fd.MFASystem):

    def compute(self):
        """
        Perform all computations for the MFA system in sequence.
        """
        self.compute_inflows()

    def compute_inflows(self):

        # Abbreviation for better readability
        prm = self.parameters
        flw = self.flows
        stk = self.stock

        # Define auxiliary flows for the MFA system in addition to the main flows defined in plastics_definition.py
        aux = {
            "DomesticInputManufacturing": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ImportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "ExportNew": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
            "NetImport": self.get_new_array(dim_letters=("r", "t", "s", "p", "e")),
        }

        ### POLYMER MARKET

        flw["Environment => Polymer market"][...] = prm["DomesticDemand"] # F_0_1_Domestic
        flw["Polymer market => SECONDARY Plastics manufacturing"][...] = flw["Environment => Polymer market"] * prm["RecyclateShare"] # F_1_2_Recyclate
        flw["Polymer market => PRIMARY Plastics manufacturing"][...] = flw["Environment => Polymer market"] - flw["Polymer market => SECONDARY Plastics manufacturing"] # F_1_2_Primary

        ### PLASTICS MANUFACTURING
        # 1) Calculate import and export using rates applying to total domestic inputs to manufacturing
        # 2) Add absolute import and export provided exogenously
        # Note: 1) or 2) can be zero if the user only wants to use rates or absolute values.

        # Domestic input to manufacturing (primary + secondary)
        aux["DomesticInputManufacturing"] = flw["Polymer market => PRIMARY Plastics manufacturing"] + flw["Polymer market => SECONDARY Plastics manufacturing"] # InputManufacturing_1_2
        # Imports: absolute and via rates
        flw["Environment => Plastics manufacturing"][...] = prm["ImportNew"] + aux["DomesticInputManufacturing"] * prm["ImportRateNew"] # F_0_2_ImportNew
        # Exports: absolute and via rates
        flw["Plastics manufacturing => Environment"][...] = aux["DomesticInputManufacturing"] * prm["ExportRateNew"] + prm["ExportNew"] # F_2_0_ExportNew
        # Sum over all import and export regions to calculate TOTAL imports and exports and NET imports
        # ImportNew_0_2 = np.einsum('Rrtspe->rtspe', Plastics_MFA_System.FlowDict['F_0_2_ImportNew'].Values)
        # ExportNew_2_0 = np.einsum('rRtspe->rtspe', Plastics_MFA_System.FlowDict['F_2_0_ExportNew'].Values)
        aux["ImportNew"] = flw["Environment => Plastics manufacturing"].sum_to(("r","t","s","p","e"))
        aux["ExportNew"] = flw["Plastics manufacturing => Environment"].sum_to(("r","t","s","p","e"))
        aux["NetImport"] = aux["ImportNew"] - aux["ExportNew"]
        # Mass balance equation for plastics manufacturing
        flw["Plastics manufacturing => Plastics market"][...] = aux["DomesticInputManufacturing"] + aux["NetImport"] # F_2_3_NewPlastics

        ### PLASTICS MARKET

        # F_3_4_NewPlastics
        flw["Plastics market => End use stock"][...] = np.einsum('rtspe,rRtsp->Rtspe',
                                                            flw["Plastics manufacturing => Plastics market"].values,
                                                            prm["MarketShare"].values)