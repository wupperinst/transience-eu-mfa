"""
OPEN-PROM -> vehicle_inflow translation.

Moved into MIC3 from the former src/openprom; the method is unchanged.
OpenPROM -> vehicle inflow translation logic.

This is the refactored core of the original standalone ``vehicle_inflow.py``:
the exact same method, repackaged as a library function so the integrated
model can call it as a module instead of running a loose script.

It builds the EU27 + UK passenger-car inflow table (MILLIONS, 2023-2050) by
combining Eurostat 2024 new-registration data with OPEN-PROM capacity
additions.

Public API
----------
build_inflow(eurostat_path, openprom_path) -> pandas.DataFrame
    Long table with columns: Region, Vehicle type, Time, Value (million cars).
summary(df) -> list[str]
    Human-readable check lines (per-year totals, per-country, per-type).

METHOD (unchanged from the original script)
-------------------------------------------
0. WHY 2024 IS THE BASE YEAR: the OPEN-PROM results start in 2024. That makes
   2024 the only year in which a Eurostat level and an OPEN-PROM share can be
   matched to each other, so the whole table is anchored there -- 2023 is that
   base scaled backwards, 2025-2050 the OPEN-PROM trajectory scaled forwards.
   The motor-type split is OPEN-PROM's in every year; Eurostat supplies only
   the country total (and hydrogen).
1. Each country's 2024 TOTAL comes from Eurostat new-registration data
   (road_eqr_carpda), reduced by 5% to remove the van share Eurostat includes
   but the TRANSIENCE passenger-car scope does not (ICCT Pocketbook 2025/26,
   fig. 3.3).
2. That reduced total is DISTRIBUTED across motor types using OPEN-PROM 2024
   capacity-addition SHARES -- NOT Eurostat's own split.
3. Hydrogen / Fuel-Cell: 2023-2026 = Eurostat 2024 x0.95 (held flat);
   2027-2050 = OPEN-PROM hydrogen value x ratio.
4. Ethanol and Gas Turbine Kerosene (absent from OPEN-PROM) are 0.
5. UK is absent from Sheet 1, so its 2024 total is read from Sheet 2
   (cell T44 = 1,950,341), x0.95, split with UK's own OPEN-PROM shares;
   UK hydrogen = 0.
6. 2023 = 2024 base x RATIO_2023 (= 0.9877353), same motor-type mix as 2024.
7. Per-country ratio = (Eurostat 2024 total x0.95) / (OPEN-PROM 2024 sum of the
   9 non-H2 types). 2026-2050 non-H2 = OPEN-PROM[year] x ratio;
   2025 = mean(2024, 2026).
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constants (identical to the original script)
# ---------------------------------------------------------------------------
DASH = "–"  # en-dash used in the output vehicle names

# Removes the van share Eurostat includes but TRANSIENCE excludes.
# Source: ICCT Pocketbook 2025/26, fig. 3.3. Applied to every country/type.
REDUCTION = 0.95

# UK 2024 new registrations (Eurostat workbook Sheet 2, cell T44). Sheet 1 has
# no UK row, so the UK total comes from Sheet 2 instead.
UK_TOTAL_2024 = 1950341

# 2023 registrations were 1.23% below 2024; scale all 2023 rows by this ratio
# = (EU27+UK 2023 registrations) / (EU27+UK 2024). Sheet 2 cells W16:W18.
RATIO_2023 = 0.9877353

# ---- Output vehicle types (exactly the 12 in vehicle_inflow.csv) -----------
V_GAS    = f"Internal Combustion Engine {DASH} Gasoline"
V_LPG    = f"Internal Combustion Engine {DASH} Liquified Petroleum Gas"
V_DIESEL = f"Internal Combustion Engine {DASH} Diesel Oil"
V_NGAS   = f"Internal Combustion Engine {DASH} Natural Gas"
V_ETH    = f"Internal Combustion Engine {DASH} Ethanol"
V_KERO   = "Gas Turbine Kerosene"
V_H2     = f"Fuel Cells {DASH} Hydrogen"
V_EV     = "Electric Vehicle/Pure Electric Engine"
V_PHEVG  = f"Plug in Hybrid {DASH} Gasoline"
V_PHEVD  = f"Plug in Hybrid {DASH} Diesel Oil"
V_CHG    = f"Conventional Hybrid {DASH} Gasoline"
V_CHD    = f"Conventional Hybrid {DASH} Diesel Oil"

VEHICLE_ORDER = [V_GAS, V_LPG, V_DIESEL, V_NGAS, V_ETH, V_KERO, V_H2,
                 V_EV, V_PHEVG, V_PHEVD, V_CHG, V_CHD]

# OPEN-PROM variable suffix -> output vehicle type (the 9 distributable types)
OPENPROM_MAP = {
    'ICE Gasoline':                 V_GAS,
    'ICE LPG':                      V_LPG,
    'ICE Diesel':                   V_DIESEL,
    'ICE Natural Gas':              V_NGAS,
    'EVs':                          V_EV,
    'Plug-in Hybrid Gasoline':      V_PHEVG,
    'Plug-in Hybrid Diesel':        V_PHEVD,
    'Conventional Hybrid Gasoline': V_CHG,
    'Conventional Hybrid Diesel':   V_CHD,
}  # Fuel Cells - Hydrogen handled separately (Eurostat)

# Eurostat country label -> region code (EU27)
GEO_TO_CODE = {
    'Belgium': 'BEL', 'Bulgaria': 'BGR', 'Czechia': 'CZE', 'Denmark': 'DNK',
    'Germany': 'DEU', 'Estonia': 'EST', 'Ireland': 'IRL', 'Greece': 'GRC',
    'Spain': 'ESP', 'France': 'FRA', 'Croatia': 'HRV', 'Italy': 'ITA',
    'Cyprus': 'CYP', 'Latvia': 'LVA', 'Lithuania': 'LTU', 'Luxembourg': 'LUX',
    'Hungary': 'HUN', 'Malta': 'MLT', 'Netherlands': 'NLD', 'Austria': 'AUT',
    'Poland': 'POL', 'Portugal': 'PRT', 'Romania': 'ROU', 'Slovenia': 'SVN',
    'Slovakia': 'SVK', 'Finland': 'FIN', 'Sweden': 'SWE',
}
ALL_REGIONS = sorted(list(GEO_TO_CODE.values()) + ['GBR'])
YEARS = list(range(2023, 2051))

# Eurostat Sheet 1 column indices
COL_TOTAL, COL_H2 = 1, 19


def _num(x):
    """Parse a Eurostat cell to float; ':' / blank / NaN -> 0.0."""
    s = str(x).strip()
    if s in (':', '', 'nan', 'None'):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def build_inflow(eurostat_path, openprom_path):
    """Build the passenger-car inflow table from the two source workbooks.

    Parameters
    ----------
    eurostat_path, openprom_path : str | pathlib.Path
        Paths to ``Eurostat data.xlsx`` and ``Open-prom.xlsx``.

    Returns
    -------
    pandas.DataFrame
        Columns: Region, Vehicle type, Time, Value (million cars),
        sorted by (Region, Vehicle type, Time).
    """
    eurostat_path = Path(eurostat_path)
    openprom_path = Path(openprom_path)
    for p in (eurostat_path, openprom_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing OpenPROM input file: {p}")

    # -- 1. Eurostat 2024: country TOTAL and HYDROGEN -----------------------
    raw = pd.read_excel(eurostat_path, sheet_name='Sheet 1', header=None)
    euro_total, euro_h2 = {}, {}
    for r in range(10, raw.shape[0]):
        geo = raw.iloc[r, 0]
        if geo not in GEO_TO_CODE:
            continue
        code = GEO_TO_CODE[geo]
        euro_total[code] = _num(raw.iloc[r, COL_TOTAL])
        euro_h2[code] = _num(raw.iloc[r, COL_H2])

    # -- 2. OPEN-PROM capacity additions per region+type -------------------
    tv = pd.read_excel(openprom_path)
    tv = tv[tv['Variable'].astype(str)
            .str.startswith('Capacity Additions|Passenger Cars|')].copy()
    tv['Suffix'] = tv['Variable'].astype(str).str.split('|').str[-1]

    def op_series(code, suffix):
        """OPEN-PROM yearly values 2024-2050 for region+suffix (dict)."""
        sub = tv[(tv['Region'] == code) & (tv['Suffix'] == suffix)]
        if sub.empty:
            return {y: 0.0 for y in range(2024, 2051)}
        row = sub.iloc[0]
        out = {}
        for y in range(2024, 2051):
            v = row.get(str(y), 0.0)
            out[y] = 0.0 if pd.isna(v) else float(v)
        return out

    def openprom_shares_2024(code):
        """Normalized 2024 shares across the 9 distributable types (dict)."""
        vals = {vt: op_series(code, suf)[2024] for suf, vt in OPENPROM_MAP.items()}
        s = sum(vals.values())
        if s <= 0:
            return {vt: 1.0 / len(OPENPROM_MAP) for vt in OPENPROM_MAP.values()}
        return {vt: vals[vt] / s for vt in vals}

    # -- 3. 2024 base distribution (cars) per region -----------------------
    def build_base_cars(code, total_cars, h2_cars, share_code):
        out = {vt: 0.0 for vt in VEHICLE_ORDER}
        h2 = min(h2_cars, total_cars)
        out[V_H2] = h2
        remainder = max(total_cars - h2, 0.0)
        for vt, sh in openprom_shares_2024(share_code).items():
            out[vt] = remainder * sh
        return out

    base_cars = {}
    for code in GEO_TO_CODE.values():
        base_cars[code] = build_base_cars(code, euro_total[code],
                                          euro_h2[code], code)
    # UK: own OPEN-PROM shares, given total, hydrogen = 0.
    base_cars['GBR'] = build_base_cars('GBR', UK_TOTAL_2024, 0.0, 'GBR')

    # -- 4. Reduce 5%, convert to MILLIONS ---------------------------------
    base_2024 = {
        code: {vt: base_cars[code][vt] * REDUCTION / 1e6 for vt in VEHICLE_ORDER}
        for code in ALL_REGIONS
    }

    # -- 5. Per-country OPEN-PROM -> Eurostat scaling ratio (in 2024) -------
    ratio_suffix = {vt: suf for suf, vt in OPENPROM_MAP.items()}
    ratio_suffix[V_H2] = 'Fuel Cells - Hydrogen'

    def reduced_eurostat_total_M(code):
        if code == 'GBR':
            return UK_TOTAL_2024 * REDUCTION / 1e6
        return euro_total[code] * REDUCTION / 1e6

    country_ratio = {}
    for code in ALL_REGIONS:
        op_2024_9 = sum(op_series(code, suf)[2024] for suf in OPENPROM_MAP.keys())
        country_ratio[code] = (reduced_eurostat_total_M(code) / op_2024_9
                               if op_2024_9 > 0 else 0.0)

    def op_scaled(code, vt, year):
        suf = ratio_suffix.get(vt)
        if suf is None:            # Ethanol / Kerosene -> always 0
            return 0.0
        v = op_series(code, suf)[year]
        return 0.0 if pd.isna(v) else float(v) * country_ratio[code]

    # -- 6. Assemble long table --------------------------------------------
    rows = []
    for code in ALL_REGIONS:
        for vt in VEHICLE_ORDER:
            base = base_2024[code][vt]
            series = {2023: base * RATIO_2023, 2024: base}

            if vt == V_H2:
                series[2025] = base
                series[2026] = base
                for y in range(2027, 2051):
                    series[y] = op_scaled(code, vt, y)
            else:
                for y in range(2026, 2051):
                    series[y] = op_scaled(code, vt, y)
                series[2025] = (series[2024] + series[2026]) / 2.0

            for y in YEARS:
                rows.append({'Region': code, 'Vehicle type': vt,
                             'Time': y, 'Value': round(series[y], 7)})

    out = pd.DataFrame(rows)
    out['Vehicle type'] = pd.Categorical(out['Vehicle type'],
                                         categories=VEHICLE_ORDER, ordered=True)
    out = out.sort_values(['Region', 'Vehicle type', 'Time']).reset_index(drop=True)

    # attach the reduced-Eurostat totals for the summary check
    out.attrs['reduced_eurostat_total_M'] = {
        c: reduced_eurostat_total_M(c) for c in ALL_REGIONS
    }
    return out


def summary(df):
    """Return human-readable check lines for the built inflow table."""
    lines = []
    lines.append(f"Rows: {len(df)} | Regions: {df['Region'].nunique()} "
                 f"| Types: {df['Vehicle type'].nunique()}")
    for y in [2023, 2024, 2025, 2030]:
        t = df[df['Time'] == y]['Value'].sum()
        lines.append(f"  EU27+UK total {y}: {t:.6f} M ({t * 1e6:,.0f})")
    eu27 = df[(df['Time'] == 2024) & (df['Region'] != 'GBR')]['Value'].sum()
    lines.append(f"  EU27-only 2024: {eu27:.6f} M ({eu27 * 1e6:,.0f}) ; "
                 f"Eurostat 10,759,959 x0.95 = {10759959 * 0.95:,.0f}")

    reduced = df.attrs.get('reduced_eurostat_total_M', {})
    y2024 = df[df['Time'] == 2024]
    lines.append("2024 total by country (millions):")
    for code in ALL_REGIONS:
        v = y2024[y2024['Region'] == code]['Value'].sum()
        chk = reduced.get(code, float('nan'))
        lines.append(f"  {code}  {v:10.6f}   (Eurostat x{REDUCTION} = {chk:.6f})")

    lines.append("2024 total by motor type, EU27+UK (millions):")
    tot = y2024['Value'].sum()
    for vt in VEHICLE_ORDER:
        v = y2024[y2024['Vehicle type'] == vt]['Value'].sum()
        pct = (v / tot * 100) if tot else 0.0
        lines.append(f"  {vt:52} {v:10.6f}  {pct:5.1f}%")
    lines.append(f"  {'TOTAL':52} {tot:10.6f}")
    return lines
