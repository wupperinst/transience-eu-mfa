def get_definition(cfg: GeneralCfg):

    dimensions = [
        #common
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="Age cohort", dim_letter="a", dtype=str),
        #from buidlings
        fd.DimensionDefinition(name="Building type", dim_letter="b", dtype=str),
        fd.DimensionDefinition(name="Concrete product", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="Steel product", dim_letter="l", dtype=str),
        fd.DimensionDefinition(name="Insulation product", dim_letter="i", dtype=str),
        #from vehicles

        #from plastics
        fd.DimensionDefinition(name="element", dim_letter="e", dtype=str),
        fd.DimensionDefinition(name="other_region", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="polymer", dim_letter="p", dtype=str),
        fd.DimensionDefinition(name="sector", dim_letter="s", dtype=str),
        fd.DimensionDefinition(name="waste_category", dim_letter="w", dtype=str),
        fd.DimensionDefinition(name="secondary_raw_material", dim_letter="m", dtype=str),
        #from steel

        #from concrete

    ]

    processes = [
        #common
        "sysenv",
        # from buildings
        "Building stock",
        "Steel stock in buildings",
        "Concrete stock in buildings",
        "Insulation stock in buildings",
        "Glass stock in buildings",
        # from vehicles

        # from plastics
        "Polymer market",  # 1
        "Plastics manufacturing",  # 2
        "Plastics market",  # 3
        "End use stock",  # 4
        "Waste collection",  # 5
        "Waste sorting",  # 6
        "Sorted waste market",  # 7
        "Recycling",  # 8
        # from steel

        # from concrete
    ]

    flows = [
        # common
            #plastic waste market

            #concrete waste market

            #steel waste market

            #plastic demand market

            #concrete demand market

            #steel demand market

        #buildings stocks
        fd.FlowDefinition(from_process="sysenv", to_process="Steel stock in buildings",
                          dim_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="sysenv", to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o")),
        fd.FlowDefinition(from_process="sysenv", to_process="Insulation stock in buildings",
                          dim_letters=("t", "r", "i")),
        fd.FlowDefinition(from_process="sysenv", to_process="Glass stock in buildings",
                          dim_letters=("t", "r", "g")),
        fd.FlowDefinition(from_process="Steel stock in buildings", to_process="Steel stock in buildings",
                          dim_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Concrete stock in buildings",to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o")),
        fd.FlowDefinition(from_process="Steel stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Concrete stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "o")),
        fd.FlowDefinition(from_process="Insulation stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "i")),
        fd.FlowDefinition(from_process="Glass stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "g")),
        # vehicles stocks

        # plastics top down demand
        fd.FlowDefinition(from_process="sysenv", to_process="Polymer market", dim_letters=("r", "t", "s", "p", "e")),
        # F_0_1_Domestic: Domestic demand for polymers
        fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing",
                          name_override="Polymer market => PRIMARY Plastics manufacturing",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_1_2_Primary: Demand for primary polymers
        #plastics handling

        fd.FlowDefinition(from_process="Polymer market", to_process="Plastics manufacturing",
                          name_override="Polymer market => SECONDARY Plastics manufacturing",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_1_2_Recyclate: Demand for recyclates
        fd.FlowDefinition(from_process="sysenv", to_process="Plastics manufacturing",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_0_2_ImportNew: Import of new plastics
        fd.FlowDefinition(from_process="Plastics manufacturing", to_process="sysenv",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_2_0_ExportNew: Export of new plastics
        fd.FlowDefinition(from_process="Plastics manufacturing", to_process="Plastics market",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_2_3_NewPlastics: New plastic products
        fd.FlowDefinition(from_process="Plastics market", to_process="End use stock",
                          dim_letters=("r", "t", "s", "p", "e")),  # F_3_4_NewPlastics: New plastic products
        fd.FlowDefinition(from_process="sysenv", to_process="End use stock",
                          dim_letters=("o", "r", "t", "c", "s", "p", "e")),
        # F_0_4_ImportUsed: Import of used plastic products
        fd.FlowDefinition(from_process="End use stock", to_process="sysenv",
                          dim_letters=("r", "o", "t", "c", "s", "p", "e")),
        # F_4_0_ExportUsed: Export of used plastic products
        fd.FlowDefinition(from_process="End use stock", to_process="Waste collection",
                          dim_letters=("r", "t", "c", "s", "p", "e")),  # F_4_5_EOLPlastics: End-of-life plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="Waste sorting",
                          dim_letters=("r", "t", "c", "s", "p", "e")),
        # F_5_6_RecoveredEOL: Recovered end-of-life plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="sysenv",
                          dim_letters=("r", "t", "c", "s", "p", "e")),  # F_5_0_Littering: Littered plastics
        fd.FlowDefinition(from_process="Waste collection", to_process="sysenv",
                          dim_letters=("r", "t", "c", "s", "p", "e")),
        # F_5_0_DefaultTreatment: Default treatment for unsorted plastics
        fd.FlowDefinition(from_process="Waste sorting", to_process="Sorted waste market",
                          dim_letters=("r", "t", "c", "s", "p", "w", "e")),  # F_6_7_SortedEOL: Sorted EoL plastics
        fd.FlowDefinition(from_process="Waste sorting", to_process="sysenv",
                          dim_letters=("r", "t", "c", "s", "p", "w", "e")),
        # F_6_0_NotForRecycling: Not for recycling EoL plastics
        fd.FlowDefinition(from_process="Sorted waste market", to_process="Recycling",
                          dim_letters=("r", "t", "s", "p", "w", "e")),  # F_7_8_SortedEOL: Sorted EoL plastics
        fd.FlowDefinition(from_process="sysenv", to_process="Sorted waste market",
                          dim_letters=("o", "r", "t", "s", "p", "w", "e")),
        # F_0_7_ImportSorted: Import sorted EoL plastics
        fd.FlowDefinition(from_process="Sorted waste market", to_process="sysenv",
                          dim_letters=("r", "o", "t", "s", "p", "w", "e")),
        # F_7_0_ExportSorted: Export sorted EoL plastics
        fd.FlowDefinition(from_process="Recycling", to_process="sysenv", dim_letters=("r", "t", "s", "p", "m", "e")),
        # F_8_0_ProcessedEOL: Processed EoL plastics
        fd.FlowDefinition(from_process="Recycling", to_process="sysenv", dim_letters=("r", "t", "s", "p", "e")),
        # F_8_0_Losses: Recycling losses


        # steel top down demand

        # steel handling

        # concrete top down demand

        #concrete handling
    ]

    stocks = [
        # common

        # from buildings

        fd.StockDefinition(
            name="Steel stock in buildings",
            process="Steel stock in buildings",
            dim_letters=("t", "r", "l"),
            subclass=fd.SimpleFlowDrivenStock,
        ),
        fd.StockDefinition(
            name="Concrete stock in buildings",
            process="Concrete stock in buildings",
            dim_letters=("t", "r", "o"),
            subclass=fd.SimpleFlowDrivenStock,
        ),
        # from vehicles

        # from plastics
        fd.StockDefinition(
            name="End use stock",
            process_name="End use stock",
            dim_letters=("t", "c", "r", "s", "p", "e"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
        # from steel

        # from concrete
    ]

    parameters = [
        # common
        # from buildings
        fd.ParameterDefinition(name="building_inflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_outflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_steel_intensity", dim_letters=("r", "b", "a", "l")),
        fd.ParameterDefinition(name="building_concrete_intensity", dim_letters=("r", "b", "a", "o")),
        fd.ParameterDefinition(name="building_insulation_intensity", dim_letters=("r", "b", "a", "i")),
        fd.ParameterDefinition(name="building_glass_intensity", dim_letters=("r", "b", "a", "g")),
        fd.ParameterDefinition(name="building_steel_element_reuse", dim_letters=("t", "r", "l")),
        fd.ParameterDefinition(name="building_concrete_element_reuse", dim_letters=("t", "r", "o")),
        # from vehicles
        # from plastics
        #todo add growth rate

        fd.ParameterDefinition(name="DomesticDemand", dim_letters=("r", "t", "s", "p", "e")), # Domestic demand for polymers
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
        fd.ParameterDefinition(name="ExportRateSortedWaste", dim_letters=("r", "o", "t", "s", "p")), # Export rate of sorted plastic waste
        fd.ParameterDefinition(name="RecyclingConversionRate", dim_letters=("r", "t", "s", "p", "w", "m")), # Conversion rates of sorted waste to secundary raw materials
        # from steel
        # todo add growth rate
        # from concrete
        # todo add growth rate

    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )