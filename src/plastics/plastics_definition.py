import logging
import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="age-cohort", dim_letter="c", dtype=int),
        fd.DimensionDefinition(name="region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="other_region", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="polymer", dim_letter="p", dtype=str),
        fd.DimensionDefinition(name="sector", dim_letter="s", dtype=str),
        fd.DimensionDefinition(name="waste_category", dim_letter="w", dtype=str),
        fd.DimensionDefinition(name="secondary_raw_material", dim_letter="m", dtype=str),
    ]

    if not cfg.customization.prodcom:
        dimensions.append(fd.DimensionDefinition(name="element", dim_letter="e", dtype=str))
    else:
        logging.info("Including 'product' dimension for prodcom bottom-up modelling")
        dimensions.append(fd.DimensionDefinition(name="product", dim_letter="d", dtype=str))

    processes = [
        "sysenv", # 0
        "Polymer market", # 1
        "Plastics manufacturing", # 2
        "Plastics market", # 3
        "End use stock", # 4
        "Waste collection", # 5
        "Waste sorting", # 6
        "Sorted waste market", # 7
        "Recycling", # 8
    ]

    if not cfg.customization.prodcom:
        flows = [
            fd.FlowDefinition(from_process="sysenv", to_process="Polymer market", dim_letters=("r", "t", "s", "p", "e")), # F_0_1_Domestic: Domestic demand for polymers
            fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => PRIMARY Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_1_2_Primary: Demand for primary polymers
            fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => SECONDARY Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_1_2_Recyclate: Demand for recyclates
            fd.FlowDefinition(from_process="sysenv", to_process="Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_0_2_ImportNew: Import of new plastics
            fd.FlowDefinition(from_process="Plastics manufacturing", to_process="sysenv", dim_letters=("r", "t", "s", "p", "e")), # F_2_0_ExportNew: Export of new plastics
            fd.FlowDefinition(from_process="Plastics manufacturing", to_process="Plastics market", dim_letters=("r", "t", "s", "p", "e")), # F_2_3_NewPlastics: New plastic products
            fd.FlowDefinition(from_process="Plastics market", to_process="End use stock", dim_letters=("r", "t", "s", "p", "e")), # F_3_4_NewPlastics: New plastic products
            fd.FlowDefinition(from_process="sysenv", to_process="End use stock", dim_letters=("o", "r", "t", "c", "s", "p", "e")), # F_0_4_ImportUsed: Import of used plastic products
            fd.FlowDefinition(from_process="End use stock", to_process="sysenv", dim_letters=("r", "o", "t", "c", "s", "p", "e")), # F_4_0_ExportUsed: Export of used plastic products
            fd.FlowDefinition(from_process="End use stock", to_process="Waste collection", dim_letters=("t", "c", "r", "s", "p", "e")), # F_4_5_EOLPlastics: End-of-life plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="Waste sorting", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_6_RecoveredEOL: Recovered end-of-life plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="sysenv", name_override="Waste collection => LITTERING sysenv", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_0_Littering: Littered plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="sysenv", name_override="Waste collection => DEFAULT TREATMENT sysenv", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_0_DefaultTreatment: Default treatment for unsorted plastics
            fd.FlowDefinition(from_process="Waste sorting", to_process="Sorted waste market", dim_letters=("r", "t", "c", "s", "p", "w", "e")), # F_6_7_SortedEOL: Sorted EoL plastics
            fd.FlowDefinition(from_process="Waste sorting", to_process="sysenv", dim_letters=("r", "t", "c", "s", "p", "w", "e")), # F_6_0_NotForRecycling: Not for recycling EoL plastics
            fd.FlowDefinition(from_process="Sorted waste market", to_process="Recycling", dim_letters=("r", "t", "s", "p", "w", "e")), # F_7_8_SortedEOL: Sorted EoL plastics
            fd.FlowDefinition(from_process="sysenv", to_process="Sorted waste market", dim_letters=("o", "r", "t", "s", "p", "w", "e")), # F_0_7_ImportSorted: Import sorted EoL plastics
            fd.FlowDefinition(from_process="Sorted waste market", to_process="sysenv", dim_letters=("r", "o", "t", "s", "p", "w", "e")), # F_7_0_ExportSorted: Export sorted EoL plastics
            fd.FlowDefinition(from_process="Recycling", to_process="sysenv", name_override="Recycling => RECYCLATE sysenv", dim_letters=("r", "t", "s", "p", "m", "e")), # F_8_0_ProcessedEOL: Processed EoL plastics
            fd.FlowDefinition(from_process="Recycling", to_process="sysenv", name_override="Recycling => LOSSES sysenv", dim_letters=("r", "t", "s", "p", "e")), # F_8_0_Losses: Recycling losses
        ]

        stocks = [
                fd.StockDefinition(
                    name="End use stock",
                    process_name="End use stock",
                    dim_letters=("t", "r", "s", "p", "e"),
                    subclass=fd.InflowDrivenDSM,
                    lifetime_model_class=cfg.customization.lifetime_model,
                    time_letter="t",
                ),
        ]

        # If config requires production-driven then DomesticDemand is an exogenous parameter
        if cfg.customization.model_driven == "production":
            logging.debug("Production-driven model, loading prm 'DomesticDemand'")
            parameters = [fd.ParameterDefinition(name="DomesticDemand", dim_letters=("r", "t", "s", "p", "e"))] # F_0_1 Converter demand for polymers
        # If config requires inflow-driven then FinalDemand is an exogenous parameter
        elif cfg.customization.model_driven == "final_demand":
            logging.debug("Final-demand-driven model, loading prm 'FinalDemand'")
            parameters = [fd.ParameterDefinition(name="FinalDemand", dim_letters=("r", "t", "s", "p", "e"))] # F_3_4_NewPlastics: New plastic products
        elif cfg.customization.model_driven == "final_demand_with_start_value_and_growth_rate":
            logging.debug("Final-demand-driven model with start value and growth rate, loading prm 'start_value' and 'growth_rate'")
            parameters = [
                fd.ParameterDefinition(name="start_value", dim_letters=("r", "t", "s", "p", "e")), # initial value of FinalDemand
                fd.ParameterDefinition(name="growth_rate", dim_letters=("r", "t", "s", "p", "e")), # growth rate of FinalDemand
            ]
        else:
            raise ValueError(f"Unknown model_driven option in config: {cfg.customization.model_driven}")
        
        parameters.extend([
            fd.ParameterDefinition(name="RecyclateShare", dim_letters=("r", "t", "s", "p")), # Recyclate shares in demand for new polymers
            fd.ParameterDefinition(name="ImportNew", dim_letters=("o", "r", "t", "s", "p", "e")), # Import of new plastic products
            fd.ParameterDefinition(name="ExportNew", dim_letters=("r", "o", "t", "s", "p", "e")), # Export of new plastic products
            fd.ParameterDefinition(name="ImportRateNew", dim_letters=("o", "r", "t", "s", "p")), # Import rate of new plastic products
            fd.ParameterDefinition(name="ExportRateNew", dim_letters=("r", "o", "t", "s", "p")), # Export rate of new plastic products
            fd.ParameterDefinition(name="MarketShare", dim_letters=("r", "o", "t", "s", "p")), # Market shares of regions in new plastics final demand
            fd.ParameterDefinition(name="ImportUsed", dim_letters=("o", "r", "t", "c", "s", "p", "e")), # Import of used plastic products
            fd.ParameterDefinition(name="ExportUsed", dim_letters=("r", "o", "t", "c", "s", "p", "e")), # Export of used plastic products
            fd.ParameterDefinition(name="ImportRateUsed", dim_letters=("o", "r", "t", "c", "s", "p")), # Import rate of used plastic products
            fd.ParameterDefinition(name="ExportRateUsed", dim_letters=("r", "o", "t", "c", "s")), # Export of rate used plastic products
            fd.ParameterDefinition(name="Lifetime", dim_letters=("r", "s", "p")), # Plastics product lifetime (constant)
            fd.ParameterDefinition(name="Lifetime_c", dim_letters=("r", "c", "s", "p")), # Plastics product lifetime (varying for new cohorts)
            fd.ParameterDefinition(name="Lifetime_t", dim_letters=("r", "t", "s", "p")), # Plastics product lifetime (varying for all cohorts)
            fd.ParameterDefinition(name="DeprivedRate", dim_letters=("r", "t", "s", "p")), # Deprived rate of non-reachable EOL plastics
            fd.ParameterDefinition(name="EoLCollectionRate", dim_letters=("r", "t", "s", "p")), # Collection rate of end-of-life (EoL) plastics products
            fd.ParameterDefinition(name="EoLUtilisationRate", dim_letters=("r", "t", "s", "p")), # Utilisation rate of end-of-life (EoL) plastics products
            fd.ParameterDefinition(name="SortingRate", dim_letters=("r", "t", "s", "p", "w")), # Sorting rate of plastics waste
            fd.ParameterDefinition(name="ImportRateSortedWaste", dim_letters=("o", "r", "t", "s", "p", "w")), # Import rate of sorted plastic waste
            fd.ParameterDefinition(name="ExportRateSortedWaste", dim_letters=("r", "o", "t", "s", "p", "w")), # Export rate of sorted plastic waste
            fd.ParameterDefinition(name="RecyclingConversionRate", dim_letters=("r", "t", "s", "p", "w", "m")), # Conversion rates of sorted waste to secundary raw materials
        ])

    # cfg.customization.prodcom is True
    else:

        flows = [
            fd.FlowDefinition(from_process="sysenv", to_process="Polymer market", dim_letters=("r", "t", "s", "d", "p")), # F_0_1_Domestic: Domestic demand for polymers
            fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => PRIMARY Plastics manufacturing", dim_letters=("r", "t", "s", "d", "p")), # F_1_2_Primary: Demand for primary polymers
            fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => SECONDARY Plastics manufacturing", dim_letters=("r", "t", "s", "d", "p")), # F_1_2_Recyclate: Demand for recyclates
            fd.FlowDefinition(from_process="sysenv", to_process="Plastics manufacturing", dim_letters=("r", "t", "s", "d", "p")), # F_0_2_ImportNew: Import of new plastics
            fd.FlowDefinition(from_process="Plastics manufacturing", to_process="sysenv", dim_letters=("r", "t", "s", "d", "p")), # F_2_0_ExportNew: Export of new plastics
            fd.FlowDefinition(from_process="Plastics manufacturing", to_process="Plastics market", dim_letters=("r", "t", "s", "d", "p")), # F_2_3_NewPlastics: New plastic products
            fd.FlowDefinition(from_process="Plastics market", to_process="End use stock", dim_letters=("r", "t", "s", "d", "p")), # F_3_4_NewPlastics: New plastic products
            fd.FlowDefinition(from_process="sysenv", to_process="End use stock", dim_letters=("o", "r", "t", "c", "s", "d", "p")), # F_0_4_ImportUsed: Import of used plastic products
            fd.FlowDefinition(from_process="End use stock", to_process="sysenv", dim_letters=("r", "o", "t", "c", "s", "d", "p")), # F_4_0_ExportUsed: Export of used plastic products
            fd.FlowDefinition(from_process="End use stock", to_process="Waste collection", dim_letters=("t", "c", "r", "s", "d", "p")), # F_4_5_EOLPlastics: End-of-life plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="Waste sorting", dim_letters=("r", "t", "c", "s", "d", "p")), # F_5_6_RecoveredEOL: Recovered end-of-life plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="sysenv", name_override="Waste collection => LITTERING sysenv", dim_letters=("r", "t", "c", "s", "d", "p")), # F_5_0_Littering: Littered plastics
            fd.FlowDefinition(from_process="Waste collection", to_process="sysenv", name_override="Waste collection => DEFAULT TREATMENT sysenv", dim_letters=("r", "t", "c", "s", "d", "p")), # F_5_0_DefaultTreatment: Default treatment for unsorted plastics
            fd.FlowDefinition(from_process="Waste sorting", to_process="Sorted waste market", dim_letters=("r", "t", "c", "s", "d", "p", "w")), # F_6_7_SortedEOL: Sorted EoL plastics
            fd.FlowDefinition(from_process="Waste sorting", to_process="sysenv", dim_letters=("r", "t", "c", "s", "d", "p", "w")), # F_6_0_NotForRecycling: Not for recycling EoL plastics
            fd.FlowDefinition(from_process="Sorted waste market", to_process="Recycling", dim_letters=("r", "t", "s", "d", "p", "w")), # F_7_8_SortedEOL: Sorted EoL plastics
            fd.FlowDefinition(from_process="sysenv", to_process="Sorted waste market", dim_letters=("o", "r", "t", "s", "d", "p", "w")), # F_0_7_ImportSorted: Import sorted EoL plastics
            fd.FlowDefinition(from_process="Sorted waste market", to_process="sysenv", dim_letters=("r", "o", "t", "s", "d", "p", "w")), # F_7_0_ExportSorted: Export sorted EoL plastics
            fd.FlowDefinition(from_process="Recycling", to_process="sysenv", name_override="Recycling => RECYCLATE sysenv", dim_letters=("r", "t", "s", "d", "p", "m")), # F_8_0_ProcessedEOL: Processed EoL plastics
            fd.FlowDefinition(from_process="Recycling", to_process="sysenv", name_override="Recycling => LOSSES sysenv", dim_letters=("r", "t", "s", "d", "p")), # F_8_0_Losses: Recycling losses
        ]

        stocks = [
                fd.StockDefinition(
                    name="End use stock",
                    process_name="End use stock",
                    dim_letters=("t", "r", "s", "d", "p"),
                    subclass=fd.InflowDrivenDSM,
                    lifetime_model_class=cfg.customization.lifetime_model,
                    time_letter="t",
                ),
        ]

        # If config requires production-driven then DomesticDemand is an exogenous parameter
        if cfg.customization.model_driven == "production":
            logging.debug("Production-driven model, loading prm 'DomesticDemand'")
            parameters = [fd.ParameterDefinition(name="DomesticDemand", dim_letters=("r", "t", "s", "d", "p"))] # F_0_1 Converter demand for polymers
        # If config requires inflow-driven then FinalDemand is an exogenous parameter
        elif cfg.customization.model_driven == "final_demand":
            logging.debug("Final-demand-driven model, loading prm 'FinalDemand'")
            parameters = [fd.ParameterDefinition(name="FinalDemand", dim_letters=("r", "t", "s", "d", "p"))] # F_3_4_NewPlastics: New plastic products
        elif cfg.customization.model_driven == "final_demand_with_start_value_and_growth_rate":
            logging.debug("Final-demand-driven model with start value and growth rate, loading prm 'start_value' and 'growth_rate'")
            parameters = [
                fd.ParameterDefinition(name="start_value", dim_letters=("r", "t", "s", "d", "p")), # initial value of FinalDemand
                fd.ParameterDefinition(name="growth_rate", dim_letters=("r", "t", "s", "d", "p")), # growth rate of FinalDemand
            ]
        else:
            raise ValueError(f"Unknown model_driven option in config: {cfg.customization.model_driven}")


        parameters.extend([
            fd.ParameterDefinition(name="RecyclateShare", dim_letters=("r", "t", "s", "d", "p")), # Recyclate shares in demand for new polymers
            fd.ParameterDefinition(name="ImportNew", dim_letters=("o", "r", "t", "s", "d", "p")), # Import of new plastic products
            fd.ParameterDefinition(name="ExportNew", dim_letters=("r", "o", "t", "s", "d", "p")), # Export of new plastic products
            fd.ParameterDefinition(name="ImportRateNew", dim_letters=("o", "r", "t", "s", "d", "p")), # Import rate of new plastic products
            fd.ParameterDefinition(name="ExportRateNew", dim_letters=("r", "o", "t", "s", "d", "p")), # Export rate of new plastic products
            fd.ParameterDefinition(name="MarketShare", dim_letters=("r", "o", "t", "s", "d", "p")), # Market shares of regions in new plastics final demand
            fd.ParameterDefinition(name="ImportUsed", dim_letters=("o", "r", "t", "c", "s", "d", "p")), # Import of used plastic products
            fd.ParameterDefinition(name="ExportUsed", dim_letters=("r", "o", "t", "c", "s", "d", "p")), # Export of used plastic products
            fd.ParameterDefinition(name="ImportRateUsed", dim_letters=("o", "r", "t", "c", "s", "d", "p")), # Import rate of used plastic products
            fd.ParameterDefinition(name="ExportRateUsed", dim_letters=("r", "o", "t", "c", "s", "d")), # Export of rate used plastic products
            fd.ParameterDefinition(name="Lifetime", dim_letters=("r", "s", "d", "p")), # Plastics product lifetime (constant)
            fd.ParameterDefinition(name="Lifetime_c", dim_letters=("r", "c", "s", "d", "p")), # Plastics product lifetime (varying for new cohorts)
            fd.ParameterDefinition(name="Lifetime_t", dim_letters=("r", "t", "s", "d", "p")), # Plastics product lifetime (varying for all cohorts)
            fd.ParameterDefinition(name="DeprivedRate", dim_letters=("r", "t", "s", "d", "p")), # Deprived rate of non-reachable EOL plastics
            fd.ParameterDefinition(name="EoLCollectionRate", dim_letters=("r", "t", "s", "d", "p")), # Collection rate of end-of-life (EoL) plastics products
            fd.ParameterDefinition(name="EoLUtilisationRate", dim_letters=("r", "t", "s", "d", "p")), # Utilisation rate of end-of-life (EoL) plastics products
            fd.ParameterDefinition(name="SortingRate", dim_letters=("r", "t", "s", "d", "p", "w")), # Sorting rate of plastics waste
            fd.ParameterDefinition(name="ImportRateSortedWaste", dim_letters=("o", "r", "t", "s", "d", "p", "w")), # Import rate of sorted plastic waste
            fd.ParameterDefinition(name="ExportRateSortedWaste", dim_letters=("r", "o", "t", "s", "d", "p", "w")), # Export rate of sorted plastic waste
            fd.ParameterDefinition(name="RecyclingConversionRate", dim_letters=("r", "t", "s", "d", "p", "w", "m")), # Conversion rates of sorted waste to secundary raw materials
        ])

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )