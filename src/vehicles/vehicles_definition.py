import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Region", dim_letter="r", dtype=str),
        fd.DimensionDefinition(name="Vehicle type", dim_letter="v", dtype=str),
        fd.DimensionDefinition(name="Vehicle size", dim_letter="z", dtype=str),
        fd.DimensionDefinition(name="Steel product", dim_letter="l", dtype=str),
        fd.DimensionDefinition(name="Plastics product", dim_letter="d", dtype=str),
        fd.DimensionDefinition(name="Glass product", dim_letter="g", dtype=str),
    ]

    processes = [
        "sysenv",
        "Vehicle stock",
        "Steel stock in vehicles",
        "Plastics stock in vehicles",
        "Glass stock in vehicles",
    ]

    flows = [
        fd.FlowDefinition(from_process="sysenv", to_process="Vehicle stock", dim_letters=("t", "r", "v", "z")),
        fd.FlowDefinition(from_process="sysenv", to_process="Steel stock in vehicles",
                          dim_letters=("t", "r", "v", "l")),
        fd.FlowDefinition(from_process="sysenv", to_process="Plastics stock in vehicles",
                          dim_letters=("t", "r", "v", "d")),
        fd.FlowDefinition(from_process="sysenv", to_process="Glass stock in vehicles",
                          dim_letters=("t", "r", "v", "g")),
        fd.FlowDefinition(from_process="Steel stock in vehicles", to_process="sysenv",
                          dim_letters=("t", "r", "v", "l")),
        fd.FlowDefinition(from_process="Plastics stock in vehicles", to_process="sysenv",
                          dim_letters=("t", "r", "v", "d")),
        fd.FlowDefinition(from_process="Glass stock in vehicles", to_process="sysenv",
                          dim_letters=("t", "r", "v", "g")),
    ]

    stocks = [
        fd.StockDefinition(
            name="Vehicle stock",
            process="Vehicle stock",
            dim_letters=("t", "r", "v", "z"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
        fd.StockDefinition(
            name="Steel stock in vehicles",
            process="Steel stock in vehicles",
            dim_letters=("t", "r", "v", "l"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
        fd.StockDefinition(
            name="Plastics stock in vehicles",
            process="Plastics stock in vehicles",
            dim_letters=("t", "r", "v", "d"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
        fd.StockDefinition(
            name="Glass stock in vehicles",
            process="Glass stock in vehicles",
            dim_letters=("t", "r", "v", "g"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
    ]

    parameters = [
        fd.ParameterDefinition(name="vehicle_inflow", dim_letters=("t", "r", "v")),
        fd.ParameterDefinition(name="vehicle_technology_share", dim_letters=("t", "r", "z")),
        fd.ParameterDefinition(name="vehicle_lifetime_mean", dim_letters=("v",)),
        fd.ParameterDefinition(name="vehicle_lifetime_std", dim_letters=("v",)),
        fd.ParameterDefinition(name="vehicle_steel_intensity", dim_letters=("v", "z", "l")),
        fd.ParameterDefinition(name="vehicle_plastics_intensity", dim_letters=("v", "z", "d")),
        fd.ParameterDefinition(name="vehicle_glass_intensity", dim_letters=("v", "z", "g")),
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )