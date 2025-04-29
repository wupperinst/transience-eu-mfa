
import pandas as pd

class FlowCalculator:
    # Function to sanitize file names
    def sanitize_filename(filename):
        return filename.replace("=>", "_to_").replace(" ", "_")

    def project_demand(
        self,
        top_down_start_value_filepath,
        top_down_growth_rate_filepath,
        bottom_up_demand_filepath,
        result_filepath,
        material_column,
        default_sector,
        default_region='EU28',
        default_material=None,
        value_column='value',
        sector_column='End use sector',
        region_column='Region simple',
        base_year=2023,  # Added base_year as a parameter
    ):
        start_value_df = pd.read_csv(top_down_start_value_filepath)
        growth_rate_df = pd.read_csv(top_down_growth_rate_filepath)
        bottom_up_demand_df = pd.read_csv(bottom_up_demand_filepath)

        for df in [start_value_df, growth_rate_df, bottom_up_demand_df]:
            if 'Value' in df.columns:
                df.rename(columns={'Value': 'value'}, inplace=True)

        if sector_column not in bottom_up_demand_df.columns:
            bottom_up_demand_df[sector_column] = default_sector

        if material_column not in bottom_up_demand_df.columns:
            if default_material is None:
                raise ValueError(f"The '{material_column}' column is missing in bottom-up data and no default is set.")
            bottom_up_demand_df[material_column] = default_material

        if region_column not in bottom_up_demand_df.columns:
            bottom_up_demand_df[region_column] = default_region

        if region_column not in start_value_df.columns:
            start_value_df[region_column] = default_region

        if region_column not in growth_rate_df.columns:
            growth_rate_df[region_column] = default_region

        demand_base_year_df = bottom_up_demand_df[bottom_up_demand_df['Time'] == base_year]

        merged_df = pd.merge(
            start_value_df,
            growth_rate_df,
            on=[sector_column, region_column, 'Time'],
            how='left',
            suffixes=('_start', '_growth')
        )

        merged_df = pd.merge(
            merged_df,
            demand_base_year_df[[material_column, sector_column, region_column, value_column]],
            on=[material_column, sector_column, region_column],
            how='left',
            suffixes=('', '_bottom_up')
        )

        merged_df[value_column] = merged_df[value_column].fillna(0)

        merged_df['Projected value'] = (merged_df[f'{value_column}_start'] - merged_df[value_column]) * merged_df[
            f'{value_column}_growth']

        result_df = merged_df[[material_column, sector_column, region_column, 'Time', 'Projected value']]
        result_df = result_df.rename(columns={'Projected value': value_column})

        result_df.to_csv(result_filepath, index=False)
        print(f"Projected demand has been calculated and saved to {result_filepath}")

    def calculate_total_flows(
        self,
        bottom_up_filepath,
        top_down_filepath,
        output_filepath,
        default_region='EU28',
        bottom_up_end_use_sector='Buildings'
    ):
        bottom_up_df = pd.read_csv(bottom_up_filepath)
        top_down_df = pd.read_csv(top_down_filepath)

        if 'End use sector' not in bottom_up_df.columns:
            bottom_up_df['End use sector'] = bottom_up_end_use_sector

        if 'End use sector' not in top_down_df.columns:
            top_down_df['End use sector'] = 'Unspecified'

        if 'Region simple' not in bottom_up_df.columns:
            bottom_up_df['Region simple'] = default_region

        if 'Region simple' not in top_down_df.columns:
            top_down_df['Region simple'] = default_region

        required_columns = ['Time', 'Region simple', 'Concrete product simple', 'End use sector', 'value']
        bottom_up_df = bottom_up_df[required_columns]
        top_down_df = top_down_df[required_columns]

        combined_df = pd.concat([bottom_up_df, top_down_df], ignore_index=True)

        total_flows_df = combined_df.groupby(
            ['Time', 'Region simple', 'Concrete product simple', 'End use sector'], as_index=False)['value'].sum()

        total_flows_df.to_csv(output_filepath, index=False)
        print(f"Total flows have been calculated and saved to {output_filepath}")

    def map_dimensions(self, original_df, mapping_dict):
        # Step 1: Convert mapping_dict to a DataFrame
        mapping_df = pd.DataFrame(mapping_dict)

        # Convert 'factor' to numeric and fill NaN with 1.0
        mapping_df['factor'] = pd.to_numeric(mapping_df['factor'], errors='coerce').fillna(1.0)

        # Make a copy of the original_df and reset index to columns
        df_flat = original_df.reset_index()

        # Initialize a column to hold cumulative factors
        df_flat['cumulative_factor'] = 1.0

        # For each unique original_dimension in mapping_df
        for dimension in mapping_df['original_dimension'].unique():

            # Get the mappings for this dimension
            dimension_mappings = mapping_df[mapping_df['original_dimension'] == dimension]

            # Create mapping dictionaries
            element_to_target_element = dict(
                zip(dimension_mappings['original_element'], dimension_mappings['target_element']))
            element_to_factor = dict(zip(dimension_mappings['original_element'], dimension_mappings['factor']))
            target_dimension = dimension_mappings['target_dimension'].iloc[0]

            # If dimension is in df_flat columns
            if dimension in df_flat.columns:
                # Map the elements
                df_flat[dimension + '_original'] = df_flat[dimension]
                df_flat[dimension] = df_flat[dimension].map(element_to_target_element).fillna(df_flat[dimension])

                # Apply the factors
                df_flat['factor_' + dimension] = df_flat[dimension + '_original'].map(element_to_factor).fillna(1.0)
                df_flat['cumulative_factor'] *= df_flat['factor_' + dimension]

                # Rename the dimension if target_dimension is different
                if target_dimension != dimension:
                    df_flat.rename(columns={dimension: target_dimension}, inplace=True)
            else:
                print(f"Dimension '{dimension}' not found in DataFrame columns.")
                continue

        # Apply the cumulative factor to the 'Value' column
        df_flat['value'] *= df_flat['cumulative_factor']

        # Drop the helper columns used for mapping
        helper_columns = [col for col in df_flat.columns if
                          col.startswith('factor_') or col.endswith('_original') or col == 'cumulative_factor']
        df_flat.drop(columns=helper_columns, inplace=True)

        # Group by the new dimensions and sum the values to handle duplicates
        index_columns = [col for col in df_flat.columns if col != 'value']
        remapped_data = df_flat.groupby(index_columns)['value'].sum().reset_index()

        # Set the index back to the dimensions
        remapped_data.set_index(index_columns, inplace=True)

        return remapped_data

