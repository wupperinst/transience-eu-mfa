import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="Building type", dim_letter="b", dtype=str),
        fd.DimensionDefinition(name="Age cohort", dim_letter="a", dtype=str),
        fd.DimensionDefinition(name="Concrete product", dim_letter="o", dtype=str),
        fd.DimensionDefinition(name="Steel product", dim_letter="l", dtype=str),
        fd.DimensionDefinition(name="Insulation product", dim_letter="i", dtype=str),
        fd.DimensionDefinition(name="Glass product", dim_letter="g", dtype=str),
    ]

    processes = [
        "sysenv",
        "Building stock",
        "Steel stock in buildings",
        "Concrete stock in buildings",
        "Insulation stock in buildings",
        "Glass stock in buildings",
    ]

    flows = [
        fd.FlowDefinition(from_process="sysenv", to_process="Steel stock in buildings",
                          dim_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="sysenv", to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o")),
        fd.FlowDefinition(from_process="sysenv", to_process="Insulation stock in buildings",
                          dim_letters=("t", "r", "i")),
        fd.FlowDefinition(from_process="sysenv", to_process="Glass stock in buildings",
                          dim_letters=("t", "r", "g")),
        fd.FlowDefinition(from_process="Steel stock in buildings", to_process="Steel stock in buildings",
                          dim_letters=("t", "r", "l","a")),
        fd.FlowDefinition(from_process="Concrete stock in buildings",to_process="Concrete stock in buildings",
                          dim_letters=("t", "r", "o","a")),
        fd.FlowDefinition(from_process="Steel stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "l","a")),
        fd.FlowDefinition(from_process="Concrete stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "o","a")),
        fd.FlowDefinition(from_process="Insulation stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "i","a")),
        fd.FlowDefinition(from_process="Glass stock in buildings", to_process="sysenv",
                          dim_letters=("t", "r", "g","a")),
    ]

    stocks = [
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
    ]

    parameters = [
        fd.ParameterDefinition(name="building_inflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_outflow", dim_letters=("t", "r", "b", "a")),
        fd.ParameterDefinition(name="building_steel_intensity", dim_letters=("r", "b", "a", "l")),
        fd.ParameterDefinition(name="building_concrete_intensity", dim_letters=("r", "b", "a", "o")),
        fd.ParameterDefinition(name="building_insulation_intensity", dim_letters=("r", "b", "a", "i")),
        fd.ParameterDefinition(name="building_glass_intensity", dim_letters=("r", "b", "a", "g")),
        fd.ParameterDefinition(name="building_steel_element_reuse", dim_letters=("t", "r", "l")),
        fd.ParameterDefinition(name="building_concrete_element_reuse", dim_letters=("t", "r", "o")),
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )