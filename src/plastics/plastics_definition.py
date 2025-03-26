import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Age-cohort", dim_letter="c", dtype=int),
        fd.DimensionDefinition(name="element", dim_letter="e", dtype=str),
        fd.DimensionDefinition(name="region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="other Region", dim_letter="R", dtype=str),
        fd.DimensionDefinition(name="polymer", dim_letter="p", dtype=str),
        fd.DimensionDefinition(name="sector", dim_letter="s", dtype=str),
        fd.DimensionDefinition(name="Waste category", dim_letter="w", dtype=str),
        fd.DimensionDefinition(name="Secondary raw material", dim_letter="m", dtype=str),
    ]

    processes = [
        "Environment", # 0
        "Polymer market", # 1
        "Plastics manufacturing", # 2
        "Plastics market", # 3
        "End use stock", # 4
        "Waste collection", # 5
        "Waste sorting", # 6
        "Sorted waste market", # 7
        "Recycling", # 8
    ]

    flows = [
        fd.FlowDefinition(from_process="Environment", to_process="Polymer market", dim_letters=("r", "t", "s", "p", "e")), # F_0_1_Domestic: Domestic demand for polymers
        fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => PRIMARY Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_1_2_Primary: Demand for primary polymers
        fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing", name_override="Polymer market => SECONDARY Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_1_2_Recyclate: Demand for recyclates
        fd.FlowDefinition(from_process="Environment", to_process="Plastics manufacturing", dim_letters=("r", "t", "s", "p", "e")), # F_0_2_ImportNew: Import of new plastics
        fd.FlowDefinition(from_process="Plastics manufacturing", to_process="Environment", dim_letters=("r", "t", "s", "p", "e")), # F_2_0_ExportNew: Export of new plastics
        fd.FlowDefinition(from_process="Plastics manufacturing", to_process="Plastics market", dim_letters=("r", "t", "s", "p", "e")), # F_2_3_NewPlastics: New plastic products
        fd.FlowDefinition(from_process="Plastics market", to_process="End use stock", dim_letters=("r", "t", "s", "p", "e")), # F_3_4_NewPlastics: New plastic products
        fd.FlowDefinition(from_process="Environment", to_process="End use stock", dim_letters=("R", "r", "t", "c", "s", "p", "e")), # F_0_4_ImportUsed: Import of used plastic products
        fd.FlowDefinition(from_process="End use stock", to_process="Environment", dim_letters=("r", "R", "t", "c", "s", "p", "e")), # F_4_0_ExportUsed: Export of used plastic products
        fd.FlowDefinition(from_process="End use stock", to_process="Waste collection", dim_letters=("r", "t", "c", "s", "p", "e")), # F_4_5_EOLPlastics: End-of-life plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="Waste sorting", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_6_RecoveredEOL: Recovered end-of-life plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="Environment", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_0_Littering: Littered plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="Environment", dim_letters=("r", "t", "c", "s", "p", "e")), # F_5_0_DefaultTreatment: Default treatment for unsorted plastics
        fd.FlowDefinition(from_process="Waste sorting", to_process="Sorted waste market", dim_letters=("r", "t", "c", "s", "p", "w", "e")), # F_6_7_SortedEOL: Sorted EoL plastics
        fd.FlowDefinition(from_process="Waste sorting", to_process="Environment", dim_letters=("r", "t", "c", "s", "p", "w", "e")), # F_6_0_NotForRecycling: Not for recycling EoL plastics
        fd.FlowDefinition(from_process="Sorted waste market", to_process="Recycling", dim_letters=("r", "t", "s", "p", "w", "e")), # F_7_8_SortedEOL: Sorted EoL plastics
        fd.FlowDefinition(from_process="Environment", to_process="Sorted waste market", dim_letters=("r", "r", "t", "s", "p", "w", "e")), # F_0_7_ImportSorted: Import sorted EoL plastics
        fd.FlowDefinition(from_process="Sorted waste market", to_process="Environment", dim_letters=("r", "r", "t", "s", "p", "w", "e")), # F_7_0_ExportSorted: Export sorted EoL plastics
        fd.FlowDefinition(from_process="Recycling", to_process="Environment", dim_letters=("r", "t", "s", "p", "m", "e")), # F_8_0_ProcessedEOL: Processed EoL plastics
        fd.FlowDefinition(from_process="Recycling", to_process="Environment", dim_letters=("r", "t", "s", "p", "e")), # F_8_0_Losses: Recycling losses
    ]

    stocks = [
            fd.StockDefinition(
                name="End use stock",
                process_name="End use stock",
                dim_letters=("r", "t", "c", "s", "p", "e"),
                subclass=fd.InflowDrivenDSM,
                lifetime_model_class=cfg.customization.lifetime_model,
                time_letter="t",
            ),
    ]

    parameters = [
        fd.ParameterDefinition(name="DomesticDemand", dim_letters=("r", "t", "s", "p", "e")), # Domestic demand for polymers
        fd.ParameterDefinition(name="RecyclateShare", dim_letters=("r", "t", "s", "p")), # Recyclate shares in demand for new polymers
        fd.ParameterDefinition(name="ImportNew", dim_letters=("R", "r", "t", "s", "p", "e")), # Import of new plastic products
        fd.ParameterDefinition(name="ExportNew", dim_letters=("r", "R", "t", "s", "p", "e")), # Export of new plastic products
        fd.ParameterDefinition(name="ImportRateNew", dim_letters=("R", "r", "t", "s", "p")), # Import rate of new plastic products
        fd.ParameterDefinition(name="ExportRateNew", dim_letters=("r", "R", "t", "s", "p")), # Export rate of new plastic products
        fd.ParameterDefinition(name="MarketShare", dim_letters=("r", "R", "t", "s", "p")), # Market shares of regions in new plastics final demand
        fd.ParameterDefinition(name="ImportUsed", dim_letters=("R", "r", "t", "c", "s", "p", "e")), # Import of used plastic products
        fd.ParameterDefinition(name="ExportUsed", dim_letters=("r", "R", "t", "c", "s", "p", "e")), # Export of used plastic products
        fd.ParameterDefinition(name="ImportRateUsed", dim_letters=("R", "r", "t", "c", "s", "p")), # Import rate of used plastic products
        fd.ParameterDefinition(name="ExportRateUsed", dim_letters=("r", "R", "t", "c", "s", "p")), # Export of rate used plastic products
        fd.ParameterDefinition(name="Lifetime", dim_letters=("r", "s", "p")), # Plastics product lifetime (constant)
        fd.ParameterDefinition(name="Lifetime_c", dim_letters=("r", "c", "s", "p")), # Plastics product lifetime (varying for new cohorts)
        fd.ParameterDefinition(name="Lifetime_t", dim_letters=("r", "t", "s", "p")), # Plastics product lifetime (varying for all cohorts)
        fd.ParameterDefinition(name="DeprivedRate", dim_letters=("r", "t", "s", "p")), # Deprived rate of non-reachable EOL plastics
        fd.ParameterDefinition(name="EoLCollectionRate", dim_letters=("r", "t", "s", "p")), # Collection rate of end-of-life (EoL) plastics products
        fd.ParameterDefinition(name="EoLUtilisationRate", dim_letters=("r", "t", "s", "p")), # Utilisation rate of end-of-life (EoL) plastics products
        fd.ParameterDefinition(name="SortingRate", dim_letters=("r", "t", "s", "p", "w")), # Sorting rate of plastics waste
        fd.ParameterDefinition(name="ImportRateSortedWaste", dim_letters=("R", "r", "t", "s", "p", "w")), # Import rate of sorted plastic waste
        fd.ParameterDefinition(name="ExportRateSortedWaste", dim_letters=("r", "R", "t", "s", "p", "w")), # Export rate of sorted plastic waste
        fd.ParameterDefinition(name="RecyclingConversionRate", dim_letters=("r", "t", "s", "p", "w", "m")), # Conversion rates of sorted waste to secundary raw materials
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )