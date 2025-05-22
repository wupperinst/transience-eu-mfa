import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="age-cohort", dim_letter="c", dtype=int),
        fd.DimensionDefinition(name="element", dim_letter="e", dtype=str),
        fd.DimensionDefinition(name="region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="other_region", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="intermediate", dim_letter="i", dtype=str),
        fd.DimensionDefinition(name="product", dim_letter="p", dtype=str),
        fd.DimensionDefinition(name="sector", dim_letter="s", dtype=str),
        fd.DimensionDefinition(name="waste_category", dim_letter="w", dtype=str),
    ]

    processes = [
        "sysenv", # 0
        "Steel product market", # 1
        "Steel goods manufacturing", # 2
        "Steel goods market", # 3
        "End use stock", # 4
        "Waste management", # 5
    ]

    flows = [
        fd.FlowDefinition(from_process="sysenv", to_process="Steel product market", dim_letters=("r", "t", "s", "i", "p", "e")), # F_0_1_Domestic: Domestic production of steel products
        fd.FlowDefinition(from_process="sysenv", to_process="Steel product market", name_override="sysenv => IMPORT Steel product market", dim_letters=("r", "t", "s", "i", "p", "e")), # F_0_1_Import: Import of new steel products
        fd.FlowDefinition(from_process="Steel product market", to_process="sysenv", dim_letters=("r", "t", "s", "i", "p", "e")), # F_1_0: Export of new steel products
        fd.FlowDefinition(from_process="Steel product market", to_process="Steel goods manufacturing", dim_letters=("r", "t", "s", "i", "p", "e")), # F_1_2: New steel products
        fd.FlowDefinition(from_process="Steel goods manufacturing", to_process="sysenv", dim_letters=("r", "t", "s", "i", "p", "e")), # F_2_0: Generation of new steel scrap
        fd.FlowDefinition(from_process="Steel goods manufacturing", to_process="Steel goods market", dim_letters=("r", "t", "s", "i", "p", "e")), # F_2_3: New steel goods
        fd.FlowDefinition(from_process="sysenv", to_process="Steel goods market", dim_letters=("r", "t", "s", "i", "p", "e")), # F_0_3_Import: Import of new steel goods
        fd.FlowDefinition(from_process="Steel goods market", to_process="sysenv", dim_letters=("r", "t", "s", "i", "p", "e")), # F_3_0: Export of new steel goods
        fd.FlowDefinition(from_process="Steel goods market", to_process="End use stock", dim_letters=("r", "t", "s", "i", "p", "e")), # F_3_4: New steel goods
        fd.FlowDefinition(from_process="sysenv", to_process="End use stock", dim_letters=("r", "t", "c", "s", "i", "p", "e")), # F_0_4_Import: Import of used steel goods
        fd.FlowDefinition(from_process="End use stock", to_process="sysenv", dim_letters=("r", "t", "c", "s", "i", "p", "e")), # F_4_0: Lost end-of-life steel products
        fd.FlowDefinition(from_process="End use stock", to_process="Waste management", dim_letters=("t", "c", "r", "s", "i", "p", "e")), # F_4_5: Collected end-of-life steel products
        fd.FlowDefinition(from_process="Waste management", to_process="sysenv", name_override="Waste management => AVAILABLE SCRAP sysenv", dim_letters=("r", "t", "w", "e")), # F_5_0_AvailableScrap: Available sorted steel scrap
        fd.FlowDefinition(from_process="Waste management", to_process="sysenv", name_override="Waste management => LOST SCRAP sysenv", dim_letters=("r", "t", "w", "e")), # F_5_0_LostScrap: Lost sorted steel scrap
    ]

    stocks = [
            fd.StockDefinition(
                name="End use stock",
                process_name="End use stock",
                dim_letters=("t", "r", "s", "i", "p", "e"),
                subclass=fd.InflowDrivenDSM,
                lifetime_model_class=cfg.customization.lifetime_model,
                time_letter="t",
            ),
    ]

    parameters = [
        fd.ParameterDefinition(name="Lifetime", dim_letters=("r", "s", "i", "p")), # Steel product lifetime
        fd.ParameterDefinition(name="EoLRecoveryRate", dim_letters=("r", "t", "s", "i", "p")), # Recovery rate of end-of-life (EoL) steel products
        fd.ParameterDefinition(name="ScrapSortingRate", dim_letters=("r", "t", "s", "i", "p", "w")), # Sorting rate of scrap steel
        fd.ParameterDefinition(name="Contamination", dim_letters=("r", "t", "s", "i", "p", "e")), # Contamination of steel from scrap management
        fd.ParameterDefinition(name="DomesticProduction", dim_letters=("r", "t", "s", "i", "p", "e")), # Domestic production of steel products
        fd.ParameterDefinition(name="ImportNewProducts", dim_letters=("r", "t", "s", "i", "p", "e")), # Import of new steel products
        fd.ParameterDefinition(name="ImportNewGoods", dim_letters=("r", "t", "s", "i", "p", "e")), # Import of new steel goods
        fd.ParameterDefinition(name="ExportNewProducts", dim_letters=("r", "t", "s", "i", "p", "e")), # Export of new steel products
        fd.ParameterDefinition(name="ExportNewGoods", dim_letters=("r", "t", "s", "i", "p", "e")), # Export of new steel goods
        fd.ParameterDefinition(name="InitialStock", dim_letters=("r", "t", "c", "s", "i", "p", "e")), # Stock of steel products, initial modelling year
        fd.ParameterDefinition(name="NewScrapRate", dim_letters=("r", "t", "s", "i", "p")), # Rate of generation of new scrap in steel goods production
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )
