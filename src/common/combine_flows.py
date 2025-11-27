
# src/common/combine_flows.py

import logging
import os
from typing import Optional, List, Dict, Tuple
import re

import pandas as pd


class FlowCalculator:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        return filename.replace("=>", "_to_").replace(" ", "_")

    @staticmethod
    def _read_dim_items(path: str, sep: Optional[str] = None) -> List[str]:
        df = pd.read_csv(path, sep=sep or None, engine="python")
        if df.empty:
            return []
        first_col = df.columns[0]
        return df[first_col].dropna().astype(str).str.replace("\ufeff", "", regex=False).str.strip().tolist()

    # --- Region mapping (pandas) ---
    def build_region_map_df(
        self,
        mapping_csv: str,
        *,
        src_dim: str,
        tgt_dim: str,
        sep: Optional[str] = None,
    ) -> pd.DataFrame:
        m = pd.read_csv(mapping_csv, sep=sep or None, engine="python")
        m["factor"] = pd.to_numeric(m.get("factor", 1.0), errors="coerce").fillna(1.0)
        for col in ("original_dimension", "original_element", "target_dimension", "target_element"):
            if col in m.columns:
                m[col] = m[col].astype(str).str.replace("\ufeff", "", regex=False).str.strip()
        sel = m[m["original_dimension"] == src_dim].copy()
        sel = sel.rename(columns={"original_element": src_dim, "target_element": tgt_dim})
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
        df = flow_df.copy()
        if value_col not in df.columns and "Value" in df.columns:
            df = df.rename(columns={"Value": value_col})
        map_df = self.build_region_map_df(mapping_csv, src_dim=src_dim, tgt_dim=tgt_dim, sep=sep)
        # Merge on src_dim -> create target dim and factor, then scale values
        merged = df.merge(map_df, on=src_dim, how="inner")
        merged[value_col] = pd.to_numeric(merged[value_col], errors="coerce").fillna(0) * merged["factor"]
        # Replace source region with target region
        merged = merged.drop(columns=[src_dim, "factor"]).rename(columns={tgt_dim: tgt_dim})
        return merged

    # --- Products/materials mapping (pandas) ---
    def build_products_map_array(
        self,
        mapping_csv: str,
        *,
        orig_dim: str,
        target_pairs: List[Tuple[str, str]],  # [(target_dimension_col, target_element_col), ...]
        region_col: Optional[str] = None,
        dim_catalog: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,  # name -> (csv_path, sep)
        sep: Optional[str] = None,
    ) -> pd.DataFrame:
        m = pd.read_csv(mapping_csv, sep=sep or None, engine="python")
        m["factor"] = pd.to_numeric(m.get("factor", 1.0), errors="coerce").fillna(1.0)
        for c in m.columns:
            if m[c].dtype == object:
                m[c] = m[c].astype(str).str.replace("\ufeff", "", regex=False).str.strip()

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
                is_all = isinstance(tgt_elem_val, str) and tgt_elem_val.strip().lower() == "all"
                if is_all and dim_catalog and tgt_dim_name in dim_catalog:
                    csv_path, csv_sep = dim_catalog[tgt_dim_name]
                    items = self._read_dim_items(csv_path, sep=csv_sep)
                    if not items:
                        logging.warning(f"No items for dimension '{tgt_dim_name}' to expand 'all'.")
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
        aggregate: bool = True,  #  aggregate identical keys
        group_keys: Optional[List[str]] = None,  #  override keys if needed
    ) -> pd.DataFrame:
        df = flow_df.copy()
        df[value_col] = pd.to_numeric(df.get(value_col, df.get("Value", 0)), errors="coerce").fillna(0)
        map_df = mapping_df.copy()

        # Optional region selector
        if region_col and "target_region" in map_df.columns:
            reg_unique = df[region_col].astype(str).str.strip().unique()
            map_df = map_df[
                (map_df["target_region"].astype(str).str.lower() == "all")
                | (map_df["target_region"].astype(str).str.strip().isin(reg_unique))
            ]

        if "target_parameter" in map_df.columns:
            map_df = map_df.rename(columns={"target_parameter": "parameter"})

        # Merge on original dimension, add target dims, scale by factor
        merged = df.merge(map_df, on=orig_dim, how="inner")
        merged[value_col] = merged[value_col] * pd.to_numeric(merged["factor"], errors="coerce").fillna(0)
        merged = merged.drop(columns=["factor", orig_dim, "target_region"], errors="ignore")

        # Auto-detect mapped dimension columns created by the mapping
        auto_mapped_dims = [
            c for c in map_df.columns
            if c not in {orig_dim, "factor", "target_region", "target_parameter", "parameter"}
        ]
        # Keep passed target_dims plus auto-detected ones, plus any existing dims and optional parameter
        keep_cols = list(dict.fromkeys(
            (target_dims or []) + auto_mapped_dims + list(df.columns) + ["parameter", value_col]
        ))
        keep_cols = [c for c in keep_cols if c in merged.columns]
        out = merged[keep_cols].copy()
        # aggregate duplicates (e.g., same Time × Region × Product × Sector)
        if aggregate:
            keys = group_keys or [c for c in out.columns if c != value_col]
            out[value_col] = pd.to_numeric(out[value_col], errors="coerce").fillna(0)
            out = out.groupby(keys, as_index=False)[value_col].sum()

        return out

    # --- Residual future (pandas) ---
    def compute_residual_flodym(
        self,
        start_value_df: pd.DataFrame,
        bottom_up_df: pd.DataFrame,
        growth_rate_df: pd.DataFrame,
        *,
        base_year: int,
        key_cols: Tuple[str, ...] | List[str] | None = None,
        time_col: str = "Time",
        value_col: str = "value",
        default_fill: str = "Unknown",
        fill_values_per_df: Optional[Dict[str, Dict]] = None,
    ) -> pd.DataFrame:
        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in ["Value", "VALUE", "val", "growth", "Growth", "factor", "Factor"]:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame with columns {df.columns.tolist()}")
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            return df

        start_value_df = _ensure_value(start_value_df.copy())
        bottom_up_df = _ensure_value(bottom_up_df.copy())
        growth_rate_df = _ensure_value(growth_rate_df.copy())

        if time_col not in start_value_df.columns or time_col not in bottom_up_df.columns:
            raise ValueError(f"time_col '{time_col}' must exist in both start_value_df and bottom_up_df.")

        # Optional fills
        if fill_values_per_df:
            sv_fills = fill_values_per_df.get("start_value", {})
            bu_fills = fill_values_per_df.get("bottom_up", {})
            gr_fills = fill_values_per_df.get("growth_rate", {})
            for k, v in sv_fills.items():
                if k not in start_value_df.columns:
                    start_value_df[k] = v
            for k, v in bu_fills.items():
                if k not in bottom_up_df.columns:
                    bottom_up_df[k] = v
            for k, v in gr_fills.items():
                if k not in growth_rate_df.columns:
                    growth_rate_df[k] = v

        # Determine alignment keys
        if key_cols is None:
            start_keys = set(start_value_df.columns) - {value_col, time_col}
            bu_keys = set(bottom_up_df.columns) - {value_col, time_col}
            align_keys = sorted(start_keys & bu_keys)
            if not align_keys:
                logging.warning("compute_residual_flodym: no common keys found; residual computed on totals only.")
        else:
            align_keys = [k for k in key_cols if k in start_value_df.columns and k in bottom_up_df.columns]
            dropped = sorted(set(key_cols) - set(align_keys))
            if dropped:
                logging.warning(f"compute_residual_flodym: dropping keys not shared by start/bottom_up: {dropped}")

        # Base-year aggregation
        sv_base = start_value_df[start_value_df[time_col] == base_year]
        bu_base = bottom_up_df[bottom_up_df[time_col] == base_year]
        if align_keys:
            sv_base_agg = sv_base.groupby(align_keys, as_index=False)[value_col].sum().rename(columns={value_col: "start_val"})
            bu_base_agg = bu_base.groupby(align_keys, as_index=False)[value_col].sum().rename(columns={value_col: "bu_val"})
            base_merged = sv_base_agg.merge(bu_base_agg, on=align_keys, how="outer").fillna(0)
        else:
            base_merged = pd.DataFrame({"start_val": [sv_base[value_col].sum()], "bu_val": [bu_base[value_col].sum()]})

        base_merged["residual_base"] = (base_merged.get("start_val", 0) - base_merged.get("bu_val", 0)).clip(lower=0)
        residual_base = base_merged[(align_keys if align_keys else []) + ["residual_base"]]

        # Ensure base-year in growth_rate
        if base_year not in set(growth_rate_df[time_col].unique()):
            stub = growth_rate_df.iloc[:1].copy()
            stub[time_col] = base_year
            stub[value_col] = 1.0
            growth_rate_df = pd.concat([growth_rate_df, stub], ignore_index=True)

        # Broadcast growth across missing keys
        for k in (align_keys or []):
            if k not in growth_rate_df.columns:
                uniques = residual_base[[k]].drop_duplicates()
                growth_rate_df = growth_rate_df.assign(__k=1).merge(uniques.assign(__k=1), on="__k").drop(columns="__k")

        # Merge and project residual
        gr_merged = growth_rate_df.merge(residual_base, on=align_keys, how="left") if align_keys else \
            growth_rate_df.assign(residual_base=float(residual_base["residual_base"].iloc[0] if not residual_base.empty else 0))
        gr_merged["residual_base"] = gr_merged["residual_base"].fillna(0)
        gr_merged[value_col] = gr_merged["residual_base"] * gr_merged[value_col]
        gr_merged.loc[gr_merged[time_col] == base_year, value_col] = gr_merged.loc[gr_merged[time_col] == base_year, "residual_base"]

        out_cols = (align_keys if align_keys else []) + [time_col, value_col]
        return gr_merged[out_cols]

    def compute_total_future_flodym(
        self,
        *,
        key_cols: Tuple[str, ...] | List[str],
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
        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in ["Value", "VALUE", "val", "residual", "Residual"]:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame with columns {df.columns.tolist()}")
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            return df

        items: List[Tuple[str, pd.DataFrame]] = []
        if flows is not None:
            items.extend(list(flows.items()))
        if bottom_up_df is not None:
            items.append(("bottom_up", bottom_up_df))
        if residual_df is not None:
            items.append(("residual", residual_df))
        if not items:
            raise ValueError("No inputs provided. Pass 'flows' dict or bottom_up_df/residual_df.")

        normed = []
        for name, df in items:
            df = _ensure_value(df.copy())
            for k in key_cols:
                if k not in df.columns:
                    fill_val = default_fill
                    if fill_values_per_df and name in fill_values_per_df and k in fill_values_per_df[name]:
                        fill_val = fill_values_per_df[name][k]
                    df[k] = fill_val
            normed.append(df)

        cat = pd.concat(normed, ignore_index=True, sort=False)
        if base_year is not None:
            cat = cat[cat[time_col] >= base_year] if include_base_year else cat[cat[time_col] > base_year]

        needed_cols = list(key_cols) + [time_col, value_col]
        cat = cat[[c for c in cat.columns if c in needed_cols]].copy()
        total_df = cat.groupby(list(key_cols) + [time_col], as_index=False)[value_col].sum()
        return total_df

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
        if not (os.path.exists(historic_path) and os.path.exists(future_path)):
            raise FileNotFoundError(f"Files not found: {historic_path} / {future_path}")
        hist = pd.read_csv(historic_path)
        fut = pd.read_csv(future_path)



        all_cols = sorted(set(hist.columns) | set(fut.columns))
        for df in (hist, fut):
            for c in all_cols:
                if c not in df.columns:
                    df[c] = fill_value_dim if c != value_col else 0
            df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)

        combined_df = pd.concat([hist[all_cols], fut[all_cols]], ignore_index=True)
        dims = [c for c in all_cols if c != value_col]
        combined_df = combined_df.groupby(dims, as_index=False)[value_col].sum()
        combined_df.to_csv(output_path, index=False)
        logging.info(f"Combined written: {output_path}")
        return combined_df

def _parse_cohort_years(cohort_str):
    # Gibt (start_jahr, end_jahr) zurück, z.B. '1970-1989' → (1970, 1989), '2040<' → (2040, 9999)
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

def _filter_and_split_buildings_eol(df, baseyear):
    """
    Gibt nur den Teil der EoL-Flüsse zurück, der nach dem baseyear liegt.
    Falls Kohorte baseyear schneidet, wird anteilig gesplittet.
    """
    result = []
    for _, row in df.iterrows():
        start, end = _parse_cohort_years(row["Age cohort"])
        if start is None or end is None:
            continue
        # Kohorte NACH baseyear: komplett übernehmen
        if start > baseyear:
            result.append(row)
        # Kohorte enthält baseyear: Anteil nach baseyear extrahieren
        elif start <= baseyear < end:
            years_total = end - start + 1
            years_after = end - baseyear
            if years_after > 0 and years_total > 0:
                fraction = years_after / years_total
                new_row = row.copy()
                new_row["value"] = row["value"] * fraction
                new_row["Age cohort"] = f"{baseyear + 1}-{end}"
                result.append(new_row)
        # Kohorte liegt davor: ignorieren
    return pd.DataFrame(result)