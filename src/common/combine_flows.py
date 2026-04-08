# src/common/combine_flows.py

"""
Flow calculation utilities for the EU MFA Combined Model.

This module provides:
- FlowCalculator class with methods for mapping and combining flows
- Region and product mapping functions
- Residual calculation (direct multiplication and cumulative growth)
- Historic/future flow combination
- Cohort filtering utilities for buildings EOL

"""

import logging
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd


# =============================================================================

# COHORT FILTERING UTILITIES (for Buildings EOL)

# =============================================================================


def _parse_cohort_years(cohort_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse building age cohort string into (start_year, end_year).

    Examples:
        '>1945'     -> (0, 1945)
        '2040<'     -> (2040, 9999)
        '1970-1989' -> (1970, 1989)
        '2020'      -> (2020, 2020)
    """
    s = str(cohort_str).strip()

    if s.startswith(">"):
        return (0, int(s[1:]))
    if s.endswith("<"):
        return (int(s[:-1]), 9999)
    if "-" in s:
        a, b = s.split("-")
        return (int(a), int(b))
    if s.isdigit():
        y = int(s)
        return (y, y)

    return (None, None)


def filter_and_split_buildings_eol(
    df: pd.DataFrame,
    baseyear: int,
    cohort_col: str = "Age cohort",
    value_col: str = "value",
) -> pd.DataFrame:
    """
    Filter buildings EOL flows by building age cohort and baseyear.

    Returns only the part of EOL that belongs to cohorts constructed after
    the baseyear. If a cohort spans the baseyear, it is split proportionally.

    Parameters
    ----------
    df : DataFrame
        Buildings EOL flows with cohort information
    baseyear : int
        Base year for filtering (e.g., 2023)
    cohort_col : str
        Name of the cohort column (default: "Age cohort")
    value_col : str
        Name of the value column (default: "value")

    Returns
    -------
    DataFrame
        Filtered EOL flows with only post-baseyear cohorts
    """
    if cohort_col not in df.columns:
        logging.warning(
            f"Cohort column '{cohort_col}' not found. Returning original DataFrame."
        )
        return df

    results = []

    for _, row in df.iterrows():
        start, end = _parse_cohort_years(row[cohort_col])

        if start is None or end is None:
            continue

        # Cohort entirely after baseyear: keep full row
        if start > baseyear:
            results.append(row)

        # Cohort spans baseyear: keep proportional part after baseyear
        elif start <= baseyear < end:
            years_total = end - start + 1
            years_after = end - baseyear

            if years_after > 0 and years_total > 0:
                fraction = years_after / years_total
                new_row = row.copy()
                new_row[value_col] = row[value_col] * fraction
                new_row[cohort_col] = f"{baseyear + 1}-{end}"
                results.append(new_row)

        # Cohort entirely before baseyear: exclude

    if not results:
        return pd.DataFrame(columns=df.columns)

    return pd.DataFrame(results)


# =============================================================================

# FLOW CALCULATOR CLASS

# =============================================================================


class FlowCalculator:
    """
    Utility class for flow calculations in the combined MFA model.

    Provides methods for:
    - Region and product mapping
    - Residual demand calculation
    - Total future demand/EOL aggregation
    - Historic/future flow combination

    """

    # -------------------------------------------------------------------------
    # Export Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Convert flow name to valid filename."""
        return filename.replace("=>", "_to_").replace(" ", "_")

    def export_numeric_csv(
        self,
        df: pd.DataFrame,
        path: str,
        *,
        value_cols: Tuple[str, ...] = ("value",),
        float_format: str = "%.8f",
    ) -> None:
        """
        Export DataFrame to CSV with consistent numeric formatting.

        Parameters
        ----------
        df : DataFrame
            Data to export
        path : str
            Output CSV path
        value_cols : tuple of str
            Columns to cast to float
        float_format : str
            Format string for floats
        """
        df_out = df.copy()

        for col in value_cols:
            if col in df_out.columns:
                df_out[col] = pd.to_numeric(df_out[col], errors="coerce").fillna(0.0)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        df_out.to_csv(path, index=False, float_format=float_format)

    # -------------------------------------------------------------------------
    # Dimension Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _read_dim_items(path: str, sep: Optional[str] = None) -> List[str]:
        """Read dimension items from a CSV file."""
        df = pd.read_csv(path, sep=sep or None, engine="python")
        if df.empty:
            return []
        first_col = df.columns[0]
        return (
            df[first_col]
            .dropna()
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
            .tolist()
        )

    # -------------------------------------------------------------------------
    # Region Mapping
    # -------------------------------------------------------------------------

    def build_region_map_df(
        self,
        mapping_csv: str,
        *,
        src_dim: str,
        tgt_dim: str,
        sep: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Build region mapping DataFrame from CSV.

        Parameters
        ----------
        mapping_csv : str
            Path to mapping CSV
        src_dim : str
            Source dimension name (e.g., "Region")
        tgt_dim : str
            Target dimension name (e.g., "region")
        sep : str, optional
            CSV separator

        Returns
        -------
        DataFrame
            Mapping with columns [src_dim, tgt_dim, factor]
        """
        m = pd.read_csv(mapping_csv, sep=sep or None, engine="python")
        m["factor"] = pd.to_numeric(m.get("factor", 1.0), errors="coerce").fillna(1.0)

        # Clean string columns
        for col in (
            "original_dimension",
            "original_element",
            "target_dimension",
            "target_element",
        ):
            if col in m.columns:
                m[col] = (
                    m[col]
                    .astype(str)
                    .str.replace("\ufeff", "", regex=False)
                    .str.strip()
                )

        # Filter to source dimension and rename columns
        sel = m[m["original_dimension"] == src_dim].copy()
        sel = sel.rename(
            columns={"original_element": src_dim, "target_element": tgt_dim}
        )

        return sel[[src_dim, tgt_dim, "factor"]]

    def apply_region_map_array(
        self,
        flow_df: pd.DataFrame,
        *,
        src_dim: str,
        tgt_dim: str,
        mapping_csv: str,
        value_col: str = "value",
        sep: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Apply region mapping to flow DataFrame.

        Merges flow data with region mapping, scales values by factor,
        and replaces source region with target region.
        """
        df = flow_df.copy()

        # Standardize value column
        if value_col not in df.columns and "Value" in df.columns:
            df = df.rename(columns={"Value": value_col})

        map_df = self.build_region_map_df(
            mapping_csv, src_dim=src_dim, tgt_dim=tgt_dim, sep=sep
        )

        # Merge and scale
        merged = df.merge(map_df, on=src_dim, how="inner")
        merged[value_col] = (
            pd.to_numeric(merged[value_col], errors="coerce").fillna(0)
            * merged["factor"]
        )

        # Drop source dimension and factor
        merged = merged.drop(columns=[src_dim, "factor"])

        return merged

    # -------------------------------------------------------------------------
    # Product/Material Mapping
    # -------------------------------------------------------------------------

    def build_products_map_array(
        self,
        mapping_csv: str,
        *,
        orig_dim: str,
        target_pairs: List[Tuple[str, str]],
        region_col: Optional[str] = None,
        dim_catalog: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,
        sep: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Build product mapping DataFrame from CSV.

        Handles "all" expansion using dimension catalog.

        Parameters
        ----------
        mapping_csv : str
            Path to mapping CSV
        orig_dim : str
            Original dimension name (e.g., "Insulation product")
        target_pairs : list of (str, str)
            Pairs of (target_dimension_col, target_element_col)
        region_col : str, optional
            Region column name for filtering
        dim_catalog : dict, optional
            Dimension catalog for "all" expansion
        sep : str, optional
            CSV separator
        """
        m = pd.read_csv(mapping_csv, sep=sep or None, engine="python")
        m["factor"] = pd.to_numeric(m.get("factor", 1.0), errors="coerce").fillna(1.0)

        # Clean string columns
        for c in m.columns:
            if m[c].dtype == object:
                m[c] = (
                    m[c].astype(str).str.replace("\ufeff", "", regex=False).str.strip()
                )

        rows = []
        for _, r in m.iterrows():
            base = {orig_dim: r["original_element"], "factor": r["factor"]}

            if region_col and "target_region" in r and pd.notna(r["target_region"]):
                base["target_region"] = str(r["target_region"]).strip()
            if "target_parameter" in r and pd.notna(r["target_parameter"]):
                base["target_parameter"] = str(r["target_parameter"]).strip()

            parts = [base]

            for dcol, ecol in target_pairs:
                tgt_dim_name = str(r.get(dcol, "")).strip()
                tgt_elem_val = r.get(ecol, "")

                if not tgt_dim_name:
                    continue

                # Check for "all" expansion
                is_all = (
                    isinstance(tgt_elem_val, str)
                    and tgt_elem_val.strip().lower() == "all"
                )

                if is_all and dim_catalog and tgt_dim_name in dim_catalog:
                    csv_path, csv_sep = dim_catalog[tgt_dim_name]
                    items = self._read_dim_items(csv_path, sep=csv_sep)

                    if not items:
                        logging.warning(
                            f"No items for dimension '{tgt_dim_name}' to expand 'all'."
                        )
                        continue

                    new_parts = []
                    for p in parts:
                        for it in items:
                            q = dict(p)
                            q[tgt_dim_name] = it
                            new_parts.append(q)
                    parts = new_parts or parts
                else:
                    for i in range(len(parts)):
                        parts[i] = dict(parts[i])
                        parts[i][tgt_dim_name] = tgt_elem_val

            rows.extend(parts)

        return pd.DataFrame(rows)

    def apply_products_map_array(
        self,
        flow_df: pd.DataFrame,
        mapping_df: pd.DataFrame,
        *,
        orig_dim: str,
        target_dims: List[str],
        region_col: Optional[str],
        value_col: str = "value",
        aggregate: bool = True,
        group_keys: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Apply product mapping to flow DataFrame.

        Merges flow data with product mapping, scales values by factor,
        and optionally aggregates duplicate keys.
        """
        df = flow_df.copy()
        df[value_col] = pd.to_numeric(
            df.get(value_col, df.get("Value", 0)), errors="coerce"
        ).fillna(0)

        map_df = mapping_df.copy()

        # Optional region filtering
        if region_col and "target_region" in map_df.columns:
            reg_unique = df[region_col].astype(str).str.strip().unique()
            map_df = map_df[
                (map_df["target_region"].astype(str).str.lower() == "all")
                | (map_df["target_region"].astype(str).str.strip().isin(reg_unique))
            ]

        if "target_parameter" in map_df.columns:
            map_df = map_df.rename(columns={"target_parameter": "parameter"})

        # Merge and scale
        merged = df.merge(map_df, on=orig_dim, how="inner")
        merged[value_col] = merged[value_col] * pd.to_numeric(
            merged["factor"], errors="coerce"
        ).fillna(0)
        merged = merged.drop(
            columns=["factor", orig_dim, "target_region"], errors="ignore"
        )

        # Determine output columns
        auto_mapped_dims = [
            c
            for c in map_df.columns
            if c
            not in {
                orig_dim,
                "factor",
                "target_region",
                "target_parameter",
                "parameter",
            }
        ]
        keep_cols = list(
            dict.fromkeys(
                (target_dims or [])
                + auto_mapped_dims
                + list(df.columns)
                + ["parameter", value_col]
            )
        )
        keep_cols = [c for c in keep_cols if c in merged.columns]
        out = merged[keep_cols].copy()

        # Aggregate duplicates
        if aggregate:
            keys = group_keys or [c for c in out.columns if c != value_col]
            out = out.groupby(keys, as_index=False)[value_col].sum()

        return out

    # -------------------------------------------------------------------------
    # Residual Calculation
    # -------------------------------------------------------------------------

    def compute_residual_flodym(
        self,
        start_value_df: pd.DataFrame,
        bottom_up_df: pd.DataFrame,
        growth_rate_df: pd.DataFrame,
        *,
        base_year: int,
        key_cols: Optional[Tuple[str, ...]] = None,
        time_col: str = "Time",
        value_col: str = "value",
        default_fill: str = "Unknown",
        fill_values_per_df: Optional[Dict[str, Dict]] = None,
    ) -> pd.DataFrame:
        """
        Compute residual demand using DIRECT MULTIPLICATION growth.

        residual[base_year] = start_value - bottom_up
        residual[t] = residual[base_year] * growth_rate[t]

        Used for cement model.
        """

        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in [
                    "Value",
                    "VALUE",
                    "val",
                    "growth",
                    "Growth",
                    "factor",
                    "Factor",
                ]:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame")
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            return df

        start_value_df = _ensure_value(start_value_df.copy())
        bottom_up_df = _ensure_value(bottom_up_df.copy())
        growth_rate_df = _ensure_value(growth_rate_df.copy())

        if (
            time_col not in start_value_df.columns
            or time_col not in bottom_up_df.columns
        ):
            raise ValueError(f"time_col '{time_col}' must exist in both DataFrames")

        # Apply optional fills
        if fill_values_per_df:
            for name, fills in [
                ("start_value", start_value_df),
                ("bottom_up", bottom_up_df),
                ("growth_rate", growth_rate_df),
            ]:
                if name in fill_values_per_df:
                    for k, v in fill_values_per_df[name].items():
                        if k not in fills.columns:
                            fills[k] = v

        # Determine alignment keys
        if key_cols is None:
            start_keys = set(start_value_df.columns) - {value_col, time_col}
            bu_keys = set(bottom_up_df.columns) - {value_col, time_col}
            align_keys = sorted(start_keys & bu_keys)
        else:
            align_keys = [
                k
                for k in key_cols
                if k in start_value_df.columns and k in bottom_up_df.columns
            ]

        # Base-year aggregation
        sv_base = start_value_df[start_value_df[time_col] == base_year]
        bu_base = bottom_up_df[bottom_up_df[time_col] == base_year]

        if align_keys:
            sv_base_agg = (
                sv_base.groupby(align_keys, as_index=False)[value_col]
                .sum()
                .rename(columns={value_col: "start_val"})
            )
            bu_base_agg = (
                bu_base.groupby(align_keys, as_index=False)[value_col]
                .sum()
                .rename(columns={value_col: "bu_val"})
            )
            base_merged = sv_base_agg.merge(
                bu_base_agg, on=align_keys, how="outer"
            ).fillna(0)
        else:
            base_merged = pd.DataFrame(
                {
                    "start_val": [sv_base[value_col].sum()],
                    "bu_val": [bu_base[value_col].sum()],
                }
            )

        base_merged["residual_base"] = (
            base_merged["start_val"] - base_merged["bu_val"]
        ).clip(lower=0)
        residual_base = base_merged[
            (align_keys if align_keys else []) + ["residual_base"]
        ]

        # Ensure base-year in growth_rate
        if base_year not in growth_rate_df[time_col].unique():
            stub = growth_rate_df.iloc[:1].copy()
            stub[time_col] = base_year
            stub[value_col] = 1.0
            growth_rate_df = pd.concat([growth_rate_df, stub], ignore_index=True)

        # Broadcast growth across missing keys
        for k in align_keys:
            if k not in growth_rate_df.columns:
                uniques = residual_base[[k]].drop_duplicates()
                growth_rate_df = (
                    growth_rate_df.assign(__k=1)
                    .merge(uniques.assign(__k=1), on="__k")
                    .drop(columns="__k")
                )

        # Merge and project
        if align_keys:
            gr_merged = growth_rate_df.merge(residual_base, on=align_keys, how="left")
        else:
            gr_merged = growth_rate_df.assign(
                residual_base=float(
                    residual_base["residual_base"].iloc[0]
                    if not residual_base.empty
                    else 0
                )
            )

        gr_merged["residual_base"] = gr_merged["residual_base"].fillna(0)
        gr_merged[value_col] = gr_merged["residual_base"] * gr_merged[value_col]
        gr_merged.loc[gr_merged[time_col] == base_year, value_col] = gr_merged.loc[
            gr_merged[time_col] == base_year, "residual_base"
        ]

        out_cols = (align_keys if align_keys else []) + [time_col, value_col]
        return gr_merged[out_cols]

    def compute_residual_cumulative_growth(
        self,
        residual_base_df: pd.DataFrame,
        growth_rate_df: pd.DataFrame,
        *,
        base_year: int,
        max_year: int,
        key_cols: Tuple[str, ...],
        time_col: str = "time",
        value_col: str = "value",
    ) -> pd.DataFrame:
        """
        Compute residual using CUMULATIVE year-over-year growth.

        residual[base_year] = residual_base
        residual[t] = residual[t-1] * (1 + growth_rate[t])

        Used for plastics model where growth rates are year-over-year.
        """
        key_cols = list(key_cols)

        def _ensure_value(df: pd.DataFrame, name: str) -> pd.DataFrame:
            df = df.copy()
            if value_col not in df.columns:
                for alt in [
                    "Value",
                    "VALUE",
                    "val",
                    "growth",
                    "Growth",
                    "factor",
                    "Factor",
                ]:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in {name}")
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            return df

        residual_base_df = _ensure_value(residual_base_df, "residual_base_df")
        growth_rate_df = _ensure_value(growth_rate_df, "growth_rate_df")

        # Filter residual_base to base_year if needed
        if time_col in residual_base_df.columns:
            residual_base_df = residual_base_df[
                residual_base_df[time_col] == base_year
            ].drop(columns=[time_col])

        # Aggregate by key_cols
        available_keys = [k for k in key_cols if k in residual_base_df.columns]
        if available_keys:
            residual_base_df = residual_base_df.groupby(available_keys, as_index=False)[
                value_col
            ].sum()
            unique_keys = residual_base_df[available_keys].drop_duplicates()
        else:
            unique_keys = pd.DataFrame([{}])

        results = []

        for _, key_row in unique_keys.iterrows():
            key_dict = key_row.to_dict() if available_keys else {}

            # Get base residual value
            if available_keys:
                mask = pd.Series(True, index=residual_base_df.index)
                for k, v in key_dict.items():
                    mask &= residual_base_df[k] == v
                base_val = residual_base_df.loc[mask, value_col].sum()
            else:
                base_val = residual_base_df[value_col].sum()

            # Project forward
            current_value = base_val
            for year in range(base_year, max_year + 1):
                row = dict(key_dict)
                row[time_col] = year

                if year == base_year:
                    row[value_col] = current_value
                else:
                    # Get growth rate for this year
                    gr_mask = growth_rate_df[time_col] == year
                    for k, v in key_dict.items():
                        if k in growth_rate_df.columns:
                            gr_mask &= growth_rate_df[k] == v

                    rate_rows = growth_rate_df.loc[gr_mask, value_col]
                    rate = rate_rows.iloc[0] if len(rate_rows) > 0 else 0.0

                    current_value = current_value * (1 + rate)
                    row[value_col] = current_value

                results.append(row)

        result_df = pd.DataFrame(results)
        out_cols = available_keys + [time_col, value_col]
        return result_df[[c for c in out_cols if c in result_df.columns]]

    # -------------------------------------------------------------------------
    # Flow Aggregation
    # -------------------------------------------------------------------------

    def compute_total_future_flodym(
        self,
        *,
        key_cols: Tuple[str, ...],
        time_col: str = "Time",
        value_col: str = "value",
        base_year: Optional[int] = None,
        include_base_year: bool = False,
        flows: Optional[Dict[str, pd.DataFrame]] = None,
        bottom_up_df: Optional[pd.DataFrame] = None,
        residual_df: Optional[pd.DataFrame] = None,
        fill_values_per_df: Optional[Dict[str, Dict]] = None,
        default_fill: str = "Unknown",
    ) -> pd.DataFrame:
        """
        Sum multiple flow DataFrames into a total.

        Parameters
        ----------
        key_cols : tuple
            Dimension columns for aggregation
        flows : dict, optional
            Dictionary of {name: DataFrame}
        bottom_up_df, residual_df : DataFrame, optional
            Alternative to flows dict (legacy)
        base_year : int, optional
            Filter to years >= base_year
        include_base_year : bool
            If True, include base_year; else exclude
        """

        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in ["Value", "VALUE", "val", "residual", "Residual"]:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame")
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            return df

        # Collect inputs
        items: List[Tuple[str, pd.DataFrame]] = []
        if flows:
            items.extend(list(flows.items()))
        if bottom_up_df is not None:
            items.append(("bottom_up", bottom_up_df))
        if residual_df is not None:
            items.append(("residual", residual_df))

        if not items:
            raise ValueError("No inputs provided")

        # Normalize and align
        normed = []
        for name, df in items:
            df = _ensure_value(df.copy())
            for k in key_cols:
                if k not in df.columns:
                    fill_val = default_fill
                    if (
                        fill_values_per_df
                        and name in fill_values_per_df
                        and k in fill_values_per_df[name]
                    ):
                        fill_val = fill_values_per_df[name][k]
                    df[k] = fill_val
            normed.append(df)

        cat = pd.concat(normed, ignore_index=True, sort=False)

        # Time filtering
        if base_year is not None:
            if include_base_year:
                cat = cat[cat[time_col] >= base_year]
            else:
                cat = cat[cat[time_col] > base_year]

        # Aggregate
        needed_cols = list(key_cols) + [time_col, value_col]
        cat = cat[[c for c in cat.columns if c in needed_cols]].copy()
        total_df = cat.groupby(list(key_cols) + [time_col], as_index=False)[
            value_col
        ].sum()

        return total_df

    # -------------------------------------------------------------------------
    # Historic/Future Combination
    # -------------------------------------------------------------------------

    def combine_hist_future_flodym(
        self,
        historic_path: str,
        future_path: str,
        output_path: str,
        time_col: str = "Time",
        value_col: str = "value",
        fill_value_dim: str = "Unknown",
        base_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Combine historic and future flow CSVs.

        - Historic: time < base_year
        - Future: time >= base_year
        - Restrict to common regions (intersection)
        - Aggregate by all dimensions

        """
        if not (os.path.exists(historic_path) and os.path.exists(future_path)):
            raise FileNotFoundError(f"Files not found: {historic_path} / {future_path}")

        hist = pd.read_csv(historic_path)
        fut = pd.read_csv(future_path)

        # Time-based split
        if (
            base_year is not None
            and time_col in hist.columns
            and time_col in fut.columns
        ):
            hist = hist[hist[time_col] < base_year]
            fut = fut[fut[time_col] >= base_year]

        all_cols = sorted(set(hist.columns) | set(fut.columns))

        # Align columns
        for df in (hist, fut):
            for c in all_cols:
                if c not in df.columns:
                    df[c] = fill_value_dim if c != value_col else 0
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0)

        # Restrict to common regions
        if "region" in hist.columns and "region" in fut.columns:
            common_regions = sorted(set(hist["region"]) & set(fut["region"]))
            hist = hist[hist["region"].isin(common_regions)]
            fut = fut[fut["region"].isin(common_regions)]

        # Concatenate and aggregate
        combined_df = pd.concat([hist[all_cols], fut[all_cols]], ignore_index=True)
        dims = [c for c in all_cols if c != value_col]
        combined_df = combined_df.groupby(dims, as_index=False)[value_col].sum()

        combined_df.to_csv(output_path, index=False)
        logging.info(f"Combined written: {output_path}")

        return combined_df


# =============================================================================

# LEGACY COMPATIBILITY

# =============================================================================

# Keep the old function name for backward compatibility

_filter_and_split_buildings_eol = filter_and_split_buildings_eol
