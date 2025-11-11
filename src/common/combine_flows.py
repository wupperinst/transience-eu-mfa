import logging
import os
import pandas as pd
import flodym as fd  

class FlowCalculator:
    # Function to sanitize file names
    def sanitize_filename(filename):
        return filename.replace("=>", "_to_").replace(" ", "_")

    def map_dimensions(self, original_df, mapping_dict):
        mapping_df = pd.DataFrame(mapping_dict)
        mapping_df['factor'] = pd.to_numeric(mapping_df.get('factor', 1), errors='coerce').fillna(1.0)
        df_flat = original_df.reset_index() if 'value' in original_df else original_df.copy()
        if 'value' not in df_flat.columns and 'Value' in df_flat.columns:
            df_flat = df_flat.rename(columns={'Value': 'value'})
        if 'value' not in df_flat.columns:
            raise ValueError("'value' Spalte nicht gefunden für Mapping.")
        df_flat['cumulative_factor'] = 1.0
        for dimension in mapping_df['original_dimension'].unique():
            dim_map = mapping_df[mapping_df['original_dimension']==dimension]
            element_to_target = dict(zip(dim_map['original_element'], dim_map['target_element']))
            element_to_factor = dict(zip(dim_map['original_element'], dim_map['factor']))
            target_dimension = dim_map['target_dimension'].iloc[0]
            if dimension in df_flat.columns:
                df_flat[dimension + '_original'] = df_flat[dimension]
                df_flat[dimension] = df_flat[dimension].map(element_to_target).fillna(df_flat[dimension])
                df_flat['factor_' + dimension] = df_flat[dimension + '_original'].map(element_to_factor).fillna(1.0)
                df_flat['cumulative_factor'] *= df_flat['factor_' + dimension]
                if target_dimension != dimension:
                    df_flat.rename(columns={dimension: target_dimension}, inplace=True)
        df_flat['value'] = df_flat['value'] * df_flat['cumulative_factor']
        helper_cols = [c for c in df_flat.columns if c.startswith('factor_') or c.endswith('_original') or c=='cumulative_factor']
        df_flat.drop(columns=helper_cols, inplace=True)
        index_cols = [c for c in df_flat.columns if c != 'value']
        remapped = df_flat.groupby(index_cols, as_index=False)['value'].sum()
        return remapped


    def map_dimensions_dual_targets(
        self,
        original_df: pd.DataFrame,
        mapping_df: pd.DataFrame,
        value_col: str = "value",
        drop_source_dims: bool = True,
    ) -> pd.DataFrame:
        """
        Map each original_dimension/original_element to up to two target dimensions at once,
        replicating rows and multiplying by 'factor'. Overlapping factors are allowed (sum != 1).

        Mapping columns (supported):

          - original_dimension
          - original_element

          - target_dimension_1 / target_element_1
          - target_dimension_2 / target_element_2

          - OR duplicated headers: target_dimension, target_element, target_dimension.1, target_element.1
          - factor (optional; defaults to 1.0)

          - comment (ignored)

        Behavior:

          - For each rule row, filters rows where df[original_dimension] == original_element,

            writes target_element(s) into the named target_dimension(s), multiplies value by factor,
            and concatenates all splits.

          - Does not require factors to sum to 1; totals can increase (intentional overlap).

        """
        # Normalize input df
        df = original_df.reset_index() if value_col not in original_df.columns else original_df.copy()
        if value_col not in df.columns and "Value" in df.columns:
            df = df.rename(columns={"Value": value_col})
        if value_col not in df.columns:
            raise ValueError(f"Column '{value_col}' not found.")
        df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)

        # Prepare mapping
        m = mapping_df.copy()
        # Factor
        if "factor" not in m.columns:
            m["factor"] = 1.0
        m["factor"] = pd.to_numeric(m["factor"], errors="coerce").fillna(1.0)

        # Find target dimension/element pairs (support both numbered and duplicated headers)
        dim_cols = [c for c in m.columns if c.startswith("target_dimension")]
        elem_cols = [c for c in m.columns if c.startswith("target_element")]
        # If duplicates like 'target_dimension' and 'target_dimension.1' exist, include them
        dim_cols = sorted(dim_cols, key=lambda x: (x.rstrip(".0123456789"), x))
        elem_cols = sorted(elem_cols, key=lambda x: (x.rstrip(".0123456789"), x))
        pairs = []
        for i in range(min(len(dim_cols), len(elem_cols))):
            pairs.append((dim_cols[i], elem_cols[i]))
        if not pairs:
            raise ValueError("No target_dimension/target_element pairs found in mapping_df.")

        # Apply mapping per original_dimension group
        result_df = df.copy()
        for odim, grp in m.groupby("original_dimension"):
            if odim not in result_df.columns:
                continue

            # Base rows to be split for any of the listed original_elements
            orig_elements = grp["original_element"].dropna().unique()
            mask_any = result_df[odim].isin(orig_elements)
            base_rows = result_df[mask_any]
            if base_rows.empty:
                continue
            remainder = result_df[~mask_any]

            mapped_parts = []
            for _, rule in grp.iterrows():
                oe = rule["original_element"]
                sub = base_rows[base_rows[odim] == oe].copy()
                if sub.empty:
                    continue

                # Write each target pair
                for dcol, ecol in pairs:
                    tgt_dim_name = rule[dcol]
                    tgt_elem_val = rule[ecol]
                    if pd.isna(tgt_dim_name) or pd.isna(tgt_elem_val):
                        continue
                    # Create/overwrite the target dimension column using its NAME from the mapping
                    sub[str(tgt_dim_name)] = tgt_elem_val

                # Multiply by factor
                sub[value_col] = sub[value_col] * float(rule["factor"])
                mapped_parts.append(sub)

            # Replace matched rows with concatenated splits
            if mapped_parts:
                result_df = pd.concat([remainder, pd.concat(mapped_parts, ignore_index=True)], ignore_index=True)

        # Optionally drop source dimensions used in mapping
        if drop_source_dims:
            for s in m["original_dimension"].unique():
                if s in result_df.columns:
                    result_df = result_df.drop(columns=[s])

        # Aggregate over all dims except value
        idx_cols = [c for c in result_df.columns if c != value_col]
        result_df[value_col] = pd.to_numeric(result_df[value_col], errors="coerce").fillna(0)
        out = result_df.groupby(idx_cols, as_index=False)[value_col].sum()
        return out

    def map_building_flows_to_material(self, building_flows_df, mapping_csv_path,
                                      source_col='Building type', target_col='Concrete product simple',
                                      value_col='value', agg_cols=None):
        """
        Mappt Gebäudeflows (z.B. nach Gebäudetyp) auf Material-Endnutzungen (z.B. Zementprodukte)
        mittels einer Mapping-Tabelle (CSV). Gibt DataFrame mit gemappten und aggregierten Flows zurück.
        """
        mapping_df = pd.read_csv(mapping_csv_path, delimiter=';')
        # Merge: ordnet jedem Gebäudetyp die Ziel-Endnutzung zu
        merged = pd.merge(building_flows_df, mapping_df, on=source_col, how='left')
        # Aggregation: summiere nach Ziel-Endnutzung und ggf. weiteren Dimensionen
        if agg_cols is None:
            agg_cols = [c for c in merged.columns if c not in [source_col, value_col]]
            if target_col not in agg_cols:
                agg_cols.append(target_col)
        grouped = merged.groupby(agg_cols, as_index=False)[value_col].sum()
        return grouped

    def compute_residual_flodym(
        self,
        start_value_df: pd.DataFrame,
        bottom_up_df: pd.DataFrame,
        growth_rate_df: pd.DataFrame,
        *,
        base_year: int,
        key_cols: tuple | list | None = None,
        time_col: str = 'Time',
        value_col: str = 'value',
        default_fill: str = 'Unknown',
        fill_values_per_df: dict[str, dict] | None = None,
    ) -> pd.DataFrame:
        """
        Residual = (top-down at base_year) − (bottom-up at base_year), then project by growth factors.


        - If key_cols is None: auto-align on the intersection of non-value, non-time columns

          present in BOTH start_value_df and bottom_up_df (after filling).

        - fill_values_per_df lets you inject constant dims per dataset, e.g.:

            {'bottom_up': {'End use sector': 'Buildings'}}

        - Growth dims not in the residual keys are broadcast across residual combinations.

        """
        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in ['Value', 'VALUE', 'val', 'growth', 'Growth', 'factor', 'Factor']:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame with columns {df.columns.tolist()}")
            df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
            return df

        # Normalize
        start_value_df = _ensure_value(start_value_df.copy())
        bottom_up_df = _ensure_value(bottom_up_df.copy())
        growth_rate_df = _ensure_value(growth_rate_df.copy())

        if time_col not in start_value_df.columns or time_col not in bottom_up_df.columns:
            raise ValueError(f"time_col '{time_col}' must exist in both start_value_df and bottom_up_df.")

        # Inject constant dims per dataset (optional)
        if fill_values_per_df:
            sv_fills = fill_values_per_df.get('start_value', {})
            bu_fills = fill_values_per_df.get('bottom_up', {})
            gr_fills = fill_values_per_df.get('growth_rate', {})
            for k, v in sv_fills.items():
                if k not in start_value_df.columns:
                    start_value_df[k] = v
            for k, v in bu_fills.items():
                if k not in bottom_up_df.columns:
                    bottom_up_df[k] = v
            for k, v in gr_fills.items():
                if k not in growth_rate_df.columns:
                    growth_rate_df[k] = v

        # If key_cols provided, use only those present in BOTH; else find intersection
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

        # Base-year slices
        sv_base = start_value_df[start_value_df[time_col] == base_year]
        bu_base = bottom_up_df[bottom_up_df[time_col] == base_year]

        # Aggregate on align_keys
        if align_keys:
            sv_base_agg = sv_base.groupby(align_keys, as_index=False)[value_col].sum().rename(columns={value_col: 'start_val'})
            bu_base_agg = bu_base.groupby(align_keys, as_index=False)[value_col].sum().rename(columns={value_col: 'bu_val'})
            base_merged = sv_base_agg.merge(bu_base_agg, on=align_keys, how='outer').fillna(0)
        else:
            base_merged = pd.DataFrame({
                'start_val': [sv_base[value_col].sum()],
                'bu_val': [bu_base[value_col].sum()]
            })
        base_merged['residual_base'] = (base_merged.get('start_val', 0) - base_merged.get('bu_val', 0)).clip(lower=0)
        residual_base = base_merged[(align_keys if align_keys else []) + ['residual_base']]

        # Ensure base-year exists in growth
        if base_year not in set(growth_rate_df[time_col].unique()):
            stub = growth_rate_df.iloc[:1].copy()
            stub[time_col] = base_year
            stub[value_col] = 1.0
            growth_rate_df = pd.concat([growth_rate_df, stub], ignore_index=True)

        # Broadcast growth across residual keys not present in growth
        for k in (align_keys or []):
            if k not in growth_rate_df.columns:
                uniques = residual_base[[k]].drop_duplicates()
                growth_rate_df = growth_rate_df.assign(__k=1).merge(uniques.assign(__k=1), on='__k').drop(columns='__k')

        # Merge and project
        gr_merged = growth_rate_df.merge(residual_base, on=align_keys, how='left') if align_keys else \
                    growth_rate_df.assign(residual_base=float(residual_base['residual_base'].iloc[0] if not residual_base.empty else 0))
        gr_merged['residual_base'] = gr_merged['residual_base'].fillna(0)
        gr_merged[value_col] = gr_merged['residual_base'] * gr_merged[value_col]
        mask_base = (gr_merged[time_col] == base_year)
        gr_merged.loc[mask_base, value_col] = gr_merged.loc[mask_base, 'residual_base']

        out_cols = (align_keys if align_keys else []) + [time_col, value_col]
        return gr_merged[out_cols]

    def compute_total_future_flodym(
        self,
        *,
        key_cols: tuple | list,
        time_col: str = 'Time',
        value_col: str = 'value',
        base_year: int | None = None,
        include_base_year: bool = False,
        flows: dict[str, pd.DataFrame] | None = None,
        bottom_up_df: pd.DataFrame | None = None,
        residual_df: pd.DataFrame | None = None,
        fill_values_per_df: dict[str, dict] | None = None,
        default_fill: str = 'Unknown'
    ) -> pd.DataFrame:
        """
        Generic total for future flows: sum across multiple inputs after an optional base_year cut.

        Inputs:

          - key_cols: list/tuple of alignment dimensions
          - base_year: if provided, filters to years > base_year (or >= with include_base_year=True)

          - flows: dict name -> DataFrame (preferred generic path)
          - or bottom_up_df/residual_df: kept for backward compatibility

          - fill_values_per_df: optional dict of per-dataset fill values, e.g.:

              {'bottom_up': {'End use sector': 'Buildings', 'Region simple': 'EU28'},
               'residual':  {'End use sector': 'Residual',  'Region simple': 'EU28'}}

          - default_fill: fallback for any missing key column

        Returns a DataFrame grouped by key_cols + time_col with summed values.
        """
        def _ensure_value(df: pd.DataFrame) -> pd.DataFrame:
            if value_col not in df.columns:
                for alt in ['Value', 'VALUE', 'val', 'residual', 'Residual']:
                    if alt in df.columns:
                        df = df.rename(columns={alt: value_col})
                        break
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found in DataFrame with columns {df.columns.tolist()}")
            df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
            return df

        # Build a dict of inputs
        items: list[tuple[str, pd.DataFrame]] = []
        if flows is not None:
            items.extend(list(flows.items()))
        if bottom_up_df is not None:
            items.append(('bottom_up', bottom_up_df))
        if residual_df is not None:
            items.append(('residual', residual_df))
        if not items:
            raise ValueError("No inputs provided. Pass 'flows' dict or bottom_up_df/residual_df.")

        # Normalize, fill missing key columns per dataset
        normed = []
        for name, df in items:
            df = _ensure_value(df.copy())
            # Fill missing key columns
            for k in key_cols:
                if k not in df.columns:
                    fill_val = default_fill
                    if fill_values_per_df and name in fill_values_per_df and k in fill_values_per_df[name]:
                        fill_val = fill_values_per_df[name][k]
                    df[k] = fill_val
            normed.append(df)

        # Concatenate
        cat = pd.concat(normed, ignore_index=True, sort=False)

        # Optional future filter
        if base_year is not None:
            if include_base_year:
                cat = cat[cat[time_col] >= base_year]
            else:
                cat = cat[cat[time_col] > base_year]

        # Sum by keys + time
        needed_cols = list(key_cols) + [time_col, value_col]
        cat = cat[[c for c in cat.columns if c in needed_cols]].copy()
        total_df = cat.groupby(list(key_cols) + [time_col], as_index=False)[value_col].sum()

        return total_df


    def combine_hist_future_flodym(self, historic_path, future_path, output_path,
                                   time_col='Time', value_col='value',
                                   fill_value_dim='Unknown', base_year=None):
        """Kombiniert historic + future CSV via optional flodym; summiert überlappende Jahre.
        Warnung bei negativen Jahren. Schreibt output_path und gibt kombinierten DataFrame zurück.
        """
        if not (os.path.exists(historic_path) and os.path.exists(future_path)):
            raise FileNotFoundError(f"Dateien nicht gefunden: {historic_path} / {future_path}")
        hist = pd.read_csv(historic_path)
        fut = pd.read_csv(future_path)
        # Optional: für Stocks historische Jahre auf <= base_year beschränken und Zukunft > base_year
        if base_year is not None and historic_path.endswith('_stock.csv'):
            if time_col in hist.columns:
                hist = hist[hist[time_col] <= base_year]
            if time_col in fut.columns:
                fut = fut[fut[time_col] > base_year]
        # Negative Jahre prüfen
        for name, df in (('historic', hist), ('future', fut)):
            if time_col in df.columns:
                neg = df[df[time_col] < 0]
                if not neg.empty:
                    logging.warning(f"Negative Jahre in {name}: {sorted(neg[time_col].unique())}")
        # Spaltenunion
        all_cols = sorted(set(hist.columns) | set(fut.columns))
        for df in (hist, fut):
            for c in all_cols:
                if c not in df.columns:
                    df[c] = fill_value_dim if c != value_col else 0
        for df in (hist, fut):
            df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
        try:

            dims = [c for c in all_cols if c != value_col]
            da_hist = fd.from_dataframe(hist[dims + [value_col]], dims=dims, value_col=value_col)
            da_fut = fd.from_dataframe(fut[dims + [value_col]], dims=dims, value_col=value_col)
            da_comb = da_hist + da_fut
            combined_df = da_comb.to_df().reset_index()
        except Exception:
            combined_df = pd.concat([hist[all_cols], fut[all_cols]], ignore_index=True)
            dims = [c for c in all_cols if c != value_col]
            combined_df = combined_df.groupby(dims, as_index=False)[value_col].sum()
        combined_df.to_csv(output_path, index=False)
        logging.info(f"Combined geschrieben: {output_path}")
        return combined_df
