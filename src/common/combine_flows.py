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

    def compute_residual_flodym(self, start_value_df, bottom_up_df, growth_rate_df,
                                 base_year=2023,
                                 time_col='Time', value_col='value',
                                 key_cols=('Concrete product simple','End use sector','Region simple')):
        """Berechnet Residual (Basisjahr) + projiziert Werte. Falls growth_rate keine Produkt-Dimension hat,
        wird sie auf alle Produkte des Basisjahres expandiert (anstatt 'Unknown')."""
        product_col = key_cols[0]
        # Fehlende Key-Spalten in allen DF ergänzen
        default_map = {'End use sector': 'Buildings', 'Region simple': 'EU28'}
        for df in (start_value_df, bottom_up_df, growth_rate_df):
            for k in key_cols[1:]:  # Produkt separat behandeln
                if k not in df.columns:
                    df[k] = default_map.get(k, 'Unknown')
        # Value-Spalte normalisieren
        for df in (start_value_df, bottom_up_df, growth_rate_df):
            if value_col not in df.columns:
                for alt in ['Value','VALUE','val','growth','Growth','factor','Factor']:
                    if alt in df.columns:
                        df.rename(columns={alt: value_col}, inplace=True)
                        break
            if value_col not in df.columns:
                raise ValueError(f"Spalte '{value_col}' fehlt in einem Input.")
            df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
        # Basisjahr extrahieren
        start_base = start_value_df[start_value_df[time_col]==base_year]
        bu_base = bottom_up_df[bottom_up_df[time_col]==base_year]
        # Wenn Produktspalte in start_value fehlt -> Fehler
        if product_col not in start_base.columns:
            raise ValueError(f"Produktspalte '{product_col}' fehlt in start_value.")
        # Produktliste aus Basisjahr (Top-Down) nehmen
        products = sorted(start_base[product_col].unique())
        # Bottom-up fehlt Produkt? => kann nicht stimmen, aber sicherstellen
        if product_col not in bu_base.columns:
            bu_base[product_col] = products[0]
        # Falls growth_rate keine Produktspalte hat => expandieren
        if product_col not in growth_rate_df.columns:
            growth_rate_df = growth_rate_df.copy()
            growth_rate_df['__expander'] = 1
            prod_df = pd.DataFrame({product_col: products, '__expander': 1})
            growth_rate_df = growth_rate_df.merge(prod_df, on='__expander').drop(columns='__expander')
        # Merge Keys bestimmen: nur Keys, die growth_rate jetzt hat
        merge_keys = [c for c in key_cols if c in growth_rate_df.columns]
        # Residual Basisjahr je Produkt berechnen
        base_merged = start_base.merge(
            bu_base[[c for c in bu_base.columns if c in key_cols]+[value_col]],
            on=[c for c in key_cols if c in start_base.columns and c in bu_base.columns],
            how='left', suffixes=('_start','_bu')
        )
        if value_col+'_bu' not in base_merged.columns:
            base_merged[value_col+'_bu'] = 0
        base_merged[value_col+'_bu'] = pd.to_numeric(base_merged[value_col+'_bu'], errors='coerce').fillna(0)
        base_merged['residual_base'] = (base_merged[value_col+'_start'] - base_merged[value_col+'_bu']).clip(lower=0)
        residual_base = base_merged[[product_col,'End use sector','Region simple','residual_base']]
        # Growth mit residual_base verbinden
        growth_merged = growth_rate_df.merge(residual_base, on=[c for c in ['End use sector','Region simple', product_col] if c in growth_rate_df.columns], how='left')
        growth_merged['residual_base'] = growth_merged['residual_base'].fillna(0)
        growth_merged[value_col] = growth_merged['residual_base'] * growth_merged[value_col]
        # Basisjahr forcieren
        mask_base = growth_merged[time_col]==base_year
        growth_merged.loc[mask_base, value_col] = growth_merged.loc[mask_base,'residual_base']
        out_cols = list(key_cols)+[time_col, value_col]
        # Fehlende Spalten hinzufügen (z.B. wenn Region simple nicht Teil von key_cols war)
        for c in out_cols:
            if c not in growth_merged.columns:
                growth_merged[c] = 'Unknown'
        result = growth_merged[out_cols]
        return result

    def compute_total_future_flodym(self, bottom_up_df, residual_df,
                                     key_cols=('Concrete product simple','End use sector','Region simple'),
                                     time_col='Time', value_col='value',
                                     default_region='EU28', bottom_up_end_use_sector='Buildings', residual_end_use_sector='Residual'):
        """Addiert Bottom-up Future + Residual Future (Demand oder EOL)."""
        default_map = {'End use sector': bottom_up_end_use_sector, 'Region simple': default_region}
        for df, eus in ((bottom_up_df, bottom_up_end_use_sector), (residual_df, residual_end_use_sector)):
            for k in key_cols:
                if k not in df.columns:
                    if k == 'End use sector':
                        df[k] = eus
                    else:
                        df[k] = default_map.get(k, 'Unknown')
        for df in (bottom_up_df, residual_df):
            if value_col not in df.columns:
                for alt in ['Value','VALUE','val','residual','Residual']:
                    if alt in df.columns:
                        df.rename(columns={alt: value_col}, inplace=True)
                        break
            if value_col not in df.columns:
                raise ValueError(f"Spalte '{value_col}' fehlt in DataFrame (total future).")
            df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
        needed_cols = set(key_cols) | {time_col, value_col}
        bottom_up_df = bottom_up_df[[c for c in bottom_up_df.columns if c in needed_cols]].copy()
        residual_df = residual_df[[c for c in residual_df.columns if c in needed_cols]].copy()
        combined = pd.concat([bottom_up_df, residual_df], ignore_index=True)
        total_df = combined.groupby(list(key_cols)+[time_col], as_index=False)[value_col].sum()

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
