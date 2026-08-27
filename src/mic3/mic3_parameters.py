"""
Read the buildings parameters from the upstream MIC3 modules.

Sources are OPEN-GEM (the macroeconomic module) and the Product & Service (P&S)
database, which translates socioeconomic indicators into product demand.

This module only *reads and reshapes* source data. None of the stock logic
lives here -- the required stock, the new construction, the age-cohort split
and the flows are all computed inside the MFA, in BuildingsMFASystem.

Each function returns a long DataFrame whose column names are the dimension
names declared in buildings_definition.py (Time, Region, Building type,
Age cohort), which is what flodym matches on when reading a parameter CSV.
"""

import pandas as pd

YEARS = list(range(2020, 2051))
CALIBRATION_YEAR = 2020
HISTORY_YEARS = list(range(2020, 2025))

RESIDENTIAL_TYPES = ["SFH", "MFH"]
COMMERCIAL_TYPES = ["Ret", "Off", "Hot", "Edu", "Hea", "Oth"]

OPENGEM_MACRO_SHEET = "MACRO_BASE"
OPENGEM_SECTOR_SHEET = "SECTOR_BASE"
POP_VARIABLE = "POP"
POP_UNIT = 1e6                     # OpenGEM reports population in millions
OUTPUT_VARIABLE = "PROD"
REST_OF_WORLD = "ROW"

# which OpenGEM service sector drives each commercial building type
SERVICE_SECTOR = {
    "Ret": "SRV01", "Off": "SRV01", "Hot": "SRV01",
    "Edu": "SRV02", "Hea": "SRV02", "Oth": "SRV02",
}

# Excel mangles the cohort labels into numbers when the sheet is read back
COHORT_LABELS = {
    1945: ">1945", 1945969: "1945-1969", 1970989: "1970-1989",
    19902010: "1990-2010", 2012020: "2011-2020",
    ">1945": ">1945", "1945-1969": "1945-1969", "1970-1989": "1970-1989",
    "1990-2010": "1990-2010", "2011-2020": "2011-2020",
}
OLD_COHORTS = [">1945", "1945-1969", "1970-1989", "1990-2010", "2011-2020"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _year_columns(df, n_index_cols):
    """Rename the data columns of a wide sheet to integer years and index it."""
    index_cols = df.columns[:n_index_cols].tolist()
    data = df.iloc[:, n_index_cols:]
    years = [int(c) for c in data.columns if str(c).strip().isdigit()]
    data = data.iloc[:, : len(years)]
    data.columns = years
    out = pd.concat([df[index_cols], data], axis=1)
    return out.set_index(index_cols)[YEARS].astype(float)


def _interpolate_to_annual(nodes):
    """
    Linearly interpolate a frame reported at interval years to annual values.

    Node years are read off the sheet rather than hard-coded, so a future
    release on a different reporting grid still works.
    """
    annual = nodes.T.reindex(range(nodes.columns.min(), nodes.columns.max() + 1))
    annual = annual.interpolate(method="index").T
    return annual[[y for y in YEARS if y in annual.columns]]


def _to_long(wide, value_name="value"):
    """Wide (index x year) -> long with a Time column."""
    long = wide.stack().rename(value_name).reset_index()
    long = long.rename(columns={long.columns[-2]: "Time"})
    long["Time"] = long["Time"].astype(int)
    return long


# --------------------------------------------------------------------------- #
# population
# --------------------------------------------------------------------------- #
def population(opengem_path, history_path):
    """
    Population by region and year.

    Calibrated history up to 2024 from the static CSV export, OpenGEM from 2025
    onwards at the levels OpenGEM reports, linearly interpolated between its
    reporting years. Regions OpenGEM does not cover (GBR) hold their last
    calibrated value.
    """
    history = pd.read_csv(history_path)
    history = history.pivot(index="Region", columns="Year", values="value").astype(float)

    df = pd.read_excel(opengem_path, sheet_name=OPENGEM_MACRO_SHEET, header=1).iloc[:, 1:]
    df.columns = ["variable", "Region"] + [int(c) for c in df.columns[2:]]
    df = df[df["variable"] == POP_VARIABLE].drop(columns="variable")
    df = df[df["Region"] != REST_OF_WORLD].dropna(subset=["Region"])
    projection = _interpolate_to_annual(df.set_index("Region").astype(float) * POP_UNIT)

    out = history.reindex(columns=YEARS)
    projected = [y for y in YEARS if y not in HISTORY_YEARS]
    covered = history.index.intersection(projection.index)
    out.loc[covered, projected] = projection.loc[covered, projected]

    frozen = history.index.difference(projection.index)
    for region in frozen:
        out.loc[region, projected] = history.loc[region, HISTORY_YEARS[-1]]

    if out.isna().any().any():
        raise ValueError("Population has gaps after splicing history and OpenGEM")
    return _to_long(out), sorted(frozen)


def floor_space_per_capita(ps_path):
    """Floor space per capita (m2/cap) by region and year."""
    df = pd.read_excel(ps_path, sheet_name="Floor_space", header=0)
    df = df.rename(columns={df.columns[0]: "Region"}).dropna(subset=["Region"])
    return _to_long(_year_columns(df, 1))


def residential_share(ps_path):
    """SFH/MFH share of residential floor area by region, type and year."""
    df = pd.read_excel(ps_path, sheet_name="Residential_share", header=0)
    df = df.rename(columns={df.columns[0]: "Region", df.columns[1]: "Building type"})
    df = df.dropna(subset=["Region", "Building type"])
    df = df[df["Building type"].isin(RESIDENTIAL_TYPES)]
    return _to_long(_year_columns(df, 2))


# --------------------------------------------------------------------------- #
# old stock (residential + commercial in one parameter)
# --------------------------------------------------------------------------- #
def _old_stock_sheet(ps_path, sheet, building_types):
    df = pd.read_excel(ps_path, sheet_name=sheet, header=0)
    df = df.rename(columns={
        df.columns[0]: "Region",
        df.columns[1]: "Building type",
        df.columns[2]: "Age cohort",
    }).dropna(subset=["Region", "Building type", "Age cohort"])
    df = df[df["Building type"].isin(building_types)]
    df["Age cohort"] = df["Age cohort"].map(COHORT_LABELS)
    if df["Age cohort"].isna().any():
        raise ValueError(f"Unrecognised age cohort label in sheet {sheet!r}")
    df = df[df["Age cohort"].isin(OLD_COHORTS)]
    return _year_columns(df, 3)


def old_stock(ps_path):
    """Pre-2021 stock by region, building type, age cohort and year."""
    residential = _old_stock_sheet(ps_path, "Residential_old stock", RESIDENTIAL_TYPES)
    commercial = _old_stock_sheet(ps_path, "Commercial_old stock", COMMERCIAL_TYPES)
    return _to_long(pd.concat([residential, commercial]).sort_index())


# --------------------------------------------------------------------------- #
# commercial drivers
# --------------------------------------------------------------------------- #
def commercial_base_year(ps_path):
    """Commercial floor area in the calibration year, by region and type."""
    df = pd.read_excel(ps_path, sheet_name="Commercial_base year", header=0)
    df = df.rename(columns={df.columns[0]: "Region", df.columns[1]: "Building type"})
    df = df.dropna(subset=["Region", "Building type"])
    df = df[df["Building type"].isin(COMMERCIAL_TYPES)]
    out = df[["Region", "Building type", df.columns[2]]].copy()
    out.columns = ["Region", "Building type", "value"]
    out["value"] = out["value"].astype(float)
    return out


def service_output(opengem_path, regions):
    """
    OpenGEM service-sector output allocated to commercial building types.

    SRV01 drives retail, offices and hotels; SRV02 drives education, health and
    other. Reported at interval years and linearly interpolated to annual. The
    MFA turns this into a growth factor; only its relative change matters, so
    regions OpenGEM does not cover are given a flat series.
    """
    df = pd.read_excel(opengem_path, sheet_name=OPENGEM_SECTOR_SHEET, header=1).iloc[:, 1:]
    df.columns = ["variable", "sector", "Region"] + [int(c) for c in df.columns[3:]]
    sectors = sorted(set(SERVICE_SECTOR.values()))
    df = df[(df["variable"] == OUTPUT_VARIABLE) & (df["sector"].isin(sectors))]
    df = df[df["Region"] != REST_OF_WORLD].dropna(subset=["Region"])
    annual = _interpolate_to_annual(
        df.drop(columns="variable").set_index(["sector", "Region"]).astype(float)
    )

    frames = []
    missing = []
    for building_type in COMMERCIAL_TYPES:
        sector = SERVICE_SECTOR[building_type]
        for region in regions:
            if (sector, region) in annual.index:
                series = annual.loc[(sector, region)]
            else:
                series = pd.Series(1.0, index=YEARS)   # flat -> no growth
                missing.append(region)
            frames.append(pd.DataFrame({
                "Region": region,
                "Building type": building_type,
                "Time": YEARS,
                "value": series.reindex(YEARS).to_numpy(),
            }))
    return pd.concat(frames, ignore_index=True), sorted(set(missing))


# --------------------------------------------------------------------------- #
# material intensities
# --------------------------------------------------------------------------- #
# The P&S inventory sheets and the model's product dimensions name the same
# products slightly differently. Separator differences (", " vs "_") are handled
# by normalisation; these are the genuine mismatches that are not:
PRODUCT_ALIASES = {
    "steel": {
        # typo in the P&S sheet header
        "Hot rolled coild, sheet and strip": "Hot rolled coil, sheet and strip",
    },
    "concrete": {},
    "glass": {
        "Other": "Other glass",
    },
    # the model resolves insulation to a single product, so the P&S split by
    # building element is summed back together
    "insulation": {
        "Insulation (Exterior wall)": "Insulation",
        "Insulation (Roof)": "Insulation",
        "Insulation (Floor)": "Insulation",
        "Insulation (Basement)": "Insulation",
    },
}

MATERIALS = {
    "steel": "Steel product",
    "concrete": "Concrete product",
    "insulation": "Insulation product",
    "glass": "Glass product",
}


def _normalise(name):
    """Product names differ only by separators between the two sources."""
    text = str(name).replace("_", " ").replace(",", " ")
    return " ".join(text.split()).casefold()


def material_intensity(ps_path, material, product_items):
    """
    Material intensity by region, building type, age cohort and product.

    The P&S inventory sheet is wide, one column per product. Product names are
    resolved against the model's own product dimension, and anything the model
    holds as a single product (insulation) is summed back together.
    """
    product_dim = MATERIALS[material]
    sheet = pd.read_excel(ps_path, sheet_name=f"MInventory_{material}_buildings", header=0)
    sheet = sheet.rename(columns={
        sheet.columns[0]: "Region",
        sheet.columns[1]: "Building type",
        sheet.columns[2]: "Age cohort",
    })

    long = sheet.melt(
        id_vars=["Region", "Building type", "Age cohort"],
        var_name=product_dim, value_name="value",
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce").fillna(0.0)

    aliases = PRODUCT_ALIASES[material]
    lookup = {_normalise(item): item for item in product_items}

    def resolve(name):
        name = aliases.get(name, name)
        key = _normalise(name)
        if key not in lookup:
            raise ValueError(
                f"{material} product {name!r} in the P&S database does not match any "
                f"item of the model's {product_dim!r} dimension"
            )
        return lookup[key]

    long[product_dim] = long[product_dim].map(resolve)
    grouped = long.groupby(
        ["Region", "Building type", "Age cohort", product_dim], as_index=False
    )["value"].sum()
    return grouped.sort_values(["Region", "Building type", "Age cohort", product_dim])


# --------------------------------------------------------------------------- #
# vehicle material intensities
# --------------------------------------------------------------------------- #
# material -> (product dimension, does the model's parameter carry time?)
VEHICLE_MATERIALS = {
    "steel": ("Steel product", True),
    "plastics": ("Plastics product", False),
    "glass": ("Glass product", False),
}

VEHICLE_ALIASES = {
    # same typo as in the buildings inventory sheet
    "steel": {"Hot rolled coild, sheet and strip": "Hot rolled coil, sheet and strip"},
    "plastics": {},
    "glass": {},
}


def vehicle_intensity(ps_path, material, product_items, vehicle_types, years=None):
    """
    Vehicle material intensity by vehicle size, type and product.

    The P&S inventory sheet has no time dimension. Where the model's parameter
    carries one (steel), the value is broadcast across `years` unchanged, which
    is what the shipped baseline file does.

    Vehicle types the model does not carry are dropped; the caller is told which.
    """
    product_dim, _ = VEHICLE_MATERIALS[material]
    sheet = pd.read_excel(ps_path, sheet_name=f"MInventory_{material}_vehicles", header=0)
    sheet = sheet.rename(columns={
        sheet.columns[0]: "Vehicle size",
        sheet.columns[1]: "Vehicle type",
    })

    known = set(vehicle_types)
    dropped = sorted(set(sheet["Vehicle type"]) - known)
    sheet = sheet[sheet["Vehicle type"].isin(known)]

    long = sheet.melt(
        id_vars=["Vehicle size", "Vehicle type"], var_name=product_dim, value_name="Value"
    )
    long["Value"] = pd.to_numeric(long["Value"], errors="coerce").fillna(0.0)

    aliases = VEHICLE_ALIASES[material]
    lookup = {_normalise(item): item for item in product_items}

    def resolve(name):
        name = aliases.get(name, name)
        key = _normalise(name)
        if key not in lookup:
            raise ValueError(
                f"vehicle {material} product {name!r} in the P&S database does not match "
                f"any item of the model's {product_dim!r} dimension"
            )
        return lookup[key]

    long[product_dim] = long[product_dim].map(resolve)
    long = long.groupby(
        ["Vehicle size", "Vehicle type", product_dim], as_index=False
    )["Value"].sum()

    if years:
        long = long.merge(pd.DataFrame({"Time": list(years)}), how="cross")
        long = long[["Vehicle size", "Vehicle type", product_dim, "Time", "Value"]]

    sort_cols = ["Vehicle size", "Vehicle type", product_dim] + (["Time"] if years else [])
    return long.sort_values(sort_cols), dropped
