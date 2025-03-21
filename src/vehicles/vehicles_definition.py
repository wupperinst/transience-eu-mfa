import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Regions", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="Vehicle type", dim_letter="v", dtype=str),
        fd.DimensionDefinition(name="Vehicle size", dim_letter="v", dtype=str),
        fd.DimensionDefinition(name="Steel products", dim_letter="l", dtype=str),
        fd.DimensionDefinition(name="Plastics products", dim_letter="d", dtype=str),
        fd.DimensionDefinition(name="Glass products", dim_letter="g", dtype=str),
    ]

    processes = [
        "Environment",
        "Vehicle stock",
        "Steel stock in vehicles",
        "Plastics stock in vehicles",
        "Glass stock in vehicles",
    ]

    flows = [
        fd.FlowDefinition(from_process="Environment", to_process="Vehicle stock", dim_letters=("t", "r", "v", "z")),
        fd.FlowDefinition(from_process="Environment", to_process="Steel stock in vehicles",
                          im_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Environment", to_process="Plastics stock in vehicles",
                          dim_letters=("t", "r", "d")),
        fd.FlowDefinition(from_process="Environment", to_process="Glass stock in vehicles",
                          dim_letters=("t", "r", "g")),
        fd.FlowDefinition(from_process="Steel stock in vehicles", to_process="Environment",
                          im_letters=("t", "r", "l")),
        fd.FlowDefinition(from_process="Plastics stock in vehicles", to_process="Environment",
                          dim_letters=("t", "r", "d")),
        fd.FlowDefinition(from_process="Glass stock in vehicles", to_process="Environment",
                          dim_letters=("t", "r", "g")),
    ]

    stocks = [
        fd.StockDefinition(
            name="Vehicle stock",
            process="Vehicle stock",
            dim_letters=("t", "r", "v", "z"),
        ),
        fd.StockDefinition(
            name="Steel stock in vehicles",
            process="Steel stock in vehicles",
            dim_letters=("t", "r", "l"),
        ),
        fd.StockDefinition(
            name="Plastics stock in vehicles",
            process="Plastics stock in vehicles",
            dim_letters=("t", "r", "d"),
        ),
        fd.StockDefinition(
            name="Glass stock in vehicles",
            process="Glass stock in vehicles",
            dim_letters=("t", "r", "g"),
        ),
    ]

    parameters = [
        fd.ParameterDefinition(name="vehicle_inflow", dim_letters=("t", "r", "v")),
        fd.ParameterDefinition(name="vehicle_technology_share", dim_letters=("t", "r", "z")),
        fd.ParameterDefinition(name="vehicle_lifetime_mean", dim_letters=("v")),
        fd.ParameterDefinition(name="vehicle_lifetime_std", dim_letters=("v")),
        fd.ParameterDefinition(name="vehicle_steel_intensity", dim_letters=("v", "z", "l")),
        fd.ParameterDefinition(name="vehicle_plastics_intensity", dim_letters=("v", "z", "i")),
        fd.ParameterDefinition(name="vehicle_glass_intensity", dim_letters=("v", "z", "g")),
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )