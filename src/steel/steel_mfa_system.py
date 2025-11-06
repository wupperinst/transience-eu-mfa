import flodym as fd
import numpy as np
import logging


class SteelMFASystem(fd.MFASystem):

    def compute(self):
        """
        Perform all computations for the MFA system in sequence.
        """
        #self.interpolate_parameters()
        self.compute_inflows()
        self.compute_stock()
        self.compute_outflows()

    def compute_inflows(self):
        """
        Compute flows up to final consumption entering the stock.
        """
        
        logging.info("mfa_system - compute_inflows")

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
            "ContaminatedScrap": self.get_new_array(dim_letters=("r", "t", "s", "i", "p", "e")),
        }

        ### EOL STEEL
        logging.info("mfa_system - EOL STEEL")

        flw["End use stock => Waste management"].set_values(stk["End use stock"]._outflow_by_cohort)

        ### WASTE MANAGEMENT
        logging.info("mfa_system - WASTE MANAGEMENT")

        # Contamination
        # Sum recovered EoL flow over age cohorts
        aux["ContaminatedScrap"][...] = flw["End use stock => Waste management"].sum_to(("r","t","s","i","p","e"))
        # The Cu content of the flow needs to be increased with the new contamination:
        # Total Cu contamination = Cu contamination in EoL flow + Contamination factor * EoL flow
        # Element Cu has index 1 in Element classification [All, Cu]        
        # element[0] = All = steel + Cu
        aux["ContaminatedScrap"]["All"] += prm["Contamination"]["Cu"] * aux["ContaminatedScrap"]["All"]

        # aux["ContaminatedScrap"][:,:,:,:,:, 0] = (
        #     aux["ContaminatedScrap"][:,:,:,:,:, 0] +
        #     np.einsum('rtsip,rtsip->rtsip',
        #               prm["Contamination"][:,:,:,:,:, 1],
        #               aux["ContaminatedScrap"][:,:,:,:,:, 0])
        # )

        # element[1] = Cu
        aux["ContaminatedScrap"]["Cu"] += prm["Contamination"]["Cu"] * aux["ContaminatedScrap"]["All"]

        # aux["ContaminatedScrap"][..., 1] = (
        #     aux["ContaminatedScrap"][..., 1] +
        #     np.einsum('rtsip,rtsip->rtsip',
        #               prm["Contamination"][..., 1],
        #               aux["ContaminatedScrap"][..., 0])
        # )

        # Sorting scrap
        flw["Waste management => AVAILABLE SCRAP sysenv"][...] = aux["ContaminatedScrap"] * prm["ScrapSortingRate"] # F_5_0_AvailableScrap
        flw["Waste management => LOST SCRAP sysenv"][...] = aux["ContaminatedScrap"] * (1 - prm["ScrapSortingRate"]) # F_5_0_LostScrap


    def get_flows_as_dataframes(self):
        """Retrieve flows as pandas DataFrames from the MFA system."""
        return {flow_name: flow.to_df() for flow_name, flow in self.flows.items()}