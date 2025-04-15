import flodym as fd

from src.common.common_cfg import GeneralCfg


def get_definition(cfg: GeneralCfg):

    dimensions = [
        fd.DimensionDefinition(name="Time", dim_letter="t", dtype=int),
        fd.DimensionDefinition(name="Region simple", dim_letter="j", dtype=str),
        fd.DimensionDefinition(name="Concrete product simple", dim_letter="f", dtype=str),
        fd.DimensionDefinition(name="Cement product", dim_letter="x", dtype=str),
        fd.DimensionDefinition(name="Clinker product", dim_letter="y", dtype=str),
        fd.DimensionDefinition(name="End use sector", dim_letter="s", dtype=str),
        fd.DimensionDefinition(name="Concrete waste", dim_letter="h", dtype=str),
    ]

    processes = [
        "sysenv",
        "Clinker production",
        "Clinker market",
        "Cement production",
        "Cement market",
        "Concrete production",
        "Concrete market",
        "End use stock historic",
        "End use stock future",
        "CDW collection",
        "CDW unsorted market",
        "CDW separation",
        "CDW sorted market",
    ]

    flows = [
        fd.FlowDefinition(from_process="Clinker production", to_process="Clinker market",
                          dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Clinker market", to_process="Cement production",
                          dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Cement production", to_process="Cement market",
                          dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Cement market", to_process="Concrete production",
                          dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Concrete production", to_process="Concrete market",
                          dim_letters=("t", "j", "f")),
        fd.FlowDefinition(from_process="Concrete market", to_process="End use stock historic",
                          dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="End use stock historic", to_process="CDW collection",
                          dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="Concrete market", to_process="End use stock future",
                          dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="End use stock future", to_process="CDW collection",
                          dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="CDW collection", to_process="CDW unsorted market",
                          dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW unsorted market", to_process="CDW separation",
                          dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW separation", to_process="CDW sorted market",
                          dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW sorted market", to_process="sysenv",
                          dim_letters=("t", "j", "h")),
    ]

    stocks = [
        fd.StockDefinition(
            name="End use stock historic",
            dim_letters=("t", "j", "f", "s"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
        fd.StockDefinition(
            name="End use stock future",
            dim_letters=("t", "j", "f", "s"),
            subclass=fd.InflowDrivenDSM,
            lifetime_model_class=cfg.customization.lifetime_model,
            time_letter="t",
        ),
    ]

    parameters = [
        fd.ParameterDefinition(name="trade_clinker", dim_letters=("t", "j", "y")),
        fd.ParameterDefinition(name="clinker_factor", dim_letters=("t", "x", "y")),
        fd.ParameterDefinition(name="cement_production", dim_letters=("t", "j", "x")),
        fd.ParameterDefinition(name="trade_cement", dim_letters=("t", "j", "x")),
        fd.ParameterDefinition(name="cement_to_concrete", dim_letters=("f", "x")),
        fd.ParameterDefinition(name="trade_concrete", dim_letters=("f", "j", "t")),
        fd.ParameterDefinition(name="end_use_matrix", dim_letters=("f", "s", "t")),
        fd.ParameterDefinition(name="start_value", dim_letters=("f", "s", "t", "j")),
        fd.ParameterDefinition(name="growth_rate", dim_letters=("s", "t")),
        fd.ParameterDefinition(name="mapping_waste", dim_letters=("f", "h")),
        fd.ParameterDefinition(name="dissipative_losses", dim_letters=("s", "t")),
        fd.ParameterDefinition(name="trade_CDW_unsorted", dim_letters=("h", "j", "t")),
        fd.ParameterDefinition(name="separation_efficiency", dim_letters=("h", "t")),
        fd.ParameterDefinition(name="trade_CDW_sorted", dim_letters=("h", "j", "t")),
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