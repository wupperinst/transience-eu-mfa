import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Regions", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="Building type", dim_letter="b", dtype=str),
        fd.DimensionDefinition(name="Building age cohorts", dim_letter="a", dtype=str),
        fd.DimensionDefinition(name="Concrete products", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="Steel products", dim_letter="l", dtype=str),
        fd.DimensionDefinition(name="Insulation products", dim_letter="i", dtype=str),
        fd.DimensionDefinition(name="Glass products", dim_letter="g", dtype=str),
    ]

    processes = [
        "Environment",
        "Building stock",
        "Steel stock in buildings",
        "Concrete stock in buildings",
        "Insulation stock in building",
        "Glass stock in buildings",
    ]

    flows = [
        fd.FlowDefinition(from_process="Environment", to_process="Building stock", dim_letters=("t", "r", "b", "a")),
        fd.FlowDefinition(from_process="Building stock", to_process="Environment", dim_letters=("t", "r", "b", "a")),
        fd.FlowDefinition(from_process="Environment", to_process="Steel stock in buildings",
                          im_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Environment", to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o")),
        fd.FlowDefinition(from_process="Environment", to_process="Insulation stock in buildings",
                          dim_letters=("t", "r", "i")),
        fd.FlowDefinition(from_process="Environment", to_process="Glass stock in buildings",
                          dim_letters=("t", "r", "g")),
        fd.FlowDefinition(from_process="Steel stock in buildings", to_process="Steel stock in buildings",
                          dim_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Concrete stock in buildings",to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o")),
    ]

    stocks = [
        fd.StockDefinition(
            name="Building stock",
            process="Building stock",
            dim_letters=("t", "r", "b", "a"),
        ),
        fd.StockDefinition(
            name="Steel stock in buildings",
            process="Steel stock in buildings",
            dim_letters=("t", "r", "l"),
        ),
        fd.StockDefinition(
            name="Concrete stock in buildings",
            process="Concrete stock in buildings",
            dim_letters=("t", "r", "o"),
        ),
        fd.StockDefinition(
            name="Insulation stock in buildings",
            process="Insulation stock in buildings",
            dim_letters=("t", "r", "i"),
        ),
        fd.StockDefinition(
            name="Glass stock in buildings",
            process="Glass stock in buildings",
            dim_letters=("t", "r", "g"),
        ),
    ]

    parameters = [
        fd.ParameterDefinition(name="building_stock", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_inflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_outflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="steel_intensity", dim_letters=("r", "b", "a", "l")),
        fd.ParameterDefinition(name="concrete_intensity", dim_letters=("r", "b", "a", "o")),
        fd.ParameterDefinition(name="insulation_intensity", dim_letters=("r", "b", "a", "i")),
        fd.ParameterDefinition(name="glass_intensity", dim_letters=("r", "b", "a", "g")),
        fd.ParameterDefinition(name="steel_element_reuse", dim_letters=("r", "l")),
        fd.ParameterDefinition(name="concrete_element_reuse", dim_letters=("r", "o")),
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )