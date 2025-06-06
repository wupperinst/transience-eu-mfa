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
        "sysenv historic",
        "Clinker production historic",
        "Clinker market historic",
        "Cement production historic",
        "Cement market historic",
        "Concrete production historic",
        "Concrete market historic",
        "CDW collection historic",
        "CDW unsorted market historic",
        "CDW separation historic",
        "CDW sorted market historic",
        "sysenv future",
        "Clinker production future",
        "Clinker market future",
        "Cement production future",
        "Cement market future",
        "Concrete production future",
        "Concrete market future",
        "CDW collection future",
        "CDW unsorted market future",
        "CDW separation future",
        "CDW sorted market future",
        "End use stock historic",
       "End use stock future",
   ]

   flows = [
        fd.FlowDefinition(from_process="Clinker production historic", to_process="Clinker market historic",
                      dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Clinker market historic", to_process="Cement production historic",
                      dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Cement production historic", to_process="Cement market historic",
                      dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Cement market historic", to_process="Concrete production historic",
                      dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Concrete production historic", to_process="Concrete market historic",
                      dim_letters=("t", "j", "f")),
        fd.FlowDefinition(from_process="Concrete market historic", to_process="End use stock historic",
                      dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="End use stock historic", to_process="CDW collection historic",
                      dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="CDW collection historic", to_process="CDW unsorted market historic",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW unsorted market historic", to_process="CDW separation historic",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW separation historic", to_process="CDW sorted market historic",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW sorted market historic", to_process="sysenv historic",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="Clinker production future", to_process="Clinker market future",
                      dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Clinker market future", to_process="Cement production future",
                      dim_letters=("t", "j", "y")),
        fd.FlowDefinition(from_process="Cement production future", to_process="Cement market future",
                      dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Cement market future", to_process="Concrete production future",
                      dim_letters=("t", "j", "x")),
        fd.FlowDefinition(from_process="Concrete production future", to_process="Concrete market future",
                      dim_letters=("t", "j", "f")),
        fd.FlowDefinition(from_process="Concrete market future", to_process="End use stock future",
                      dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="End use stock future", to_process="CDW collection future",
                      dim_letters=("t", "j", "f", "s")),
        fd.FlowDefinition(from_process="CDW collection future", to_process="CDW unsorted market future",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW unsorted market future", to_process="CDW separation future",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW separation future", to_process="CDW sorted market future",
                      dim_letters=("t", "j", "h")),
        fd.FlowDefinition(from_process="CDW sorted market future", to_process="sysenv future",
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
   ]

   parameters = [
            fd.ParameterDefinition(name="trade_clinker", dim_letters=("t", "j", "y")),
            fd.ParameterDefinition(name="clinker_factor", dim_letters=("t", "x", "y")),
            fd.ParameterDefinition(name="cement_production", dim_letters=("t", "j", "x")),
            fd.ParameterDefinition(name="trade_cement", dim_letters=("t", "j", "x")),
            fd.ParameterDefinition(name="cement_to_concrete_historic", dim_letters=("f", "x")),
            fd.ParameterDefinition(name="cement_to_concrete_future", dim_letters=("f", "x")),
            fd.ParameterDefinition(name="trade_concrete", dim_letters=("f", "j", "t")),
            fd.ParameterDefinition(name="end_use_matrix", dim_letters=("f", "s", "t")),
            fd.ParameterDefinition(name="mapping_waste", dim_letters=("f", "h")),
            fd.ParameterDefinition(name="dissipative_losses", dim_letters=("s", "t")),
            fd.ParameterDefinition(name="trade_CDW_unsorted", dim_letters=("h", "j", "t")),
            fd.ParameterDefinition(name="separation_efficiency", dim_letters=("h", "t")),
            fd.ParameterDefinition(name="trade_CDW_sorted", dim_letters=("h", "j", "t")),
            fd.ParameterDefinition(name = "total_future_demand", dim_letters=("t", "j", "f", "s")),
            fd.ParameterDefinition(name = "total_future_eol_flows", dim_letters=("t", "j", "f", "s")),
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


