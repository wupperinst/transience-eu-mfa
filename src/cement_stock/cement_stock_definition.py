import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Region simple", dim_letter="j", dtype=str),
        fd.DimensionDefinition(name="Concrete product simple", dim_letter="f", dtype=str),
        fd.DimensionDefinition(name="End use sector", dim_letter="s", dtype=str),
    ]

    processes = [
        "sysenv",
        "Concrete market future",
        "End use stock future",
        "CDW collection future",
    ]

    flows = [
        fd.FlowDefinition(from_process="Concrete market future", to_process="End use stock future",
                          dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="End use stock future", to_process="CDW collection future",
                          dim_letters=("t", "j", "f", "s")),
    ]

    stocks = [
        fd.StockDefinition(
            name="End use stock future",
            dim_letters=("t", "j", "f", "s"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
    ]

    parameters = [
        fd.ParameterDefinition(name="end_use_lifetime_mean", dim_letters=("s",)),
        fd.ParameterDefinition(name="end_use_lifetime_std", dim_letters=("s",)),
    ]

    return fd.MFADefinition(
        dimensions=dimensions,
        processes=processes,
        flows=flows,
        stocks=stocks,
        parameters=parameters,
    )