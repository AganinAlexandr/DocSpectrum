let
    Source = fxLoadCsv(pDocSpectrumSamplesRoot & "\element_base_v0\feature_matrix_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"page_count", Int64.Type},
            {"element_count", Int64.Type},
            {"text_segment_count", Int64.Type},
            {"table_count", Int64.Type},
            {"table_cell_count", Int64.Type},
            {"image_count", Int64.Type},
            {"elements_per_page", type number},
            {"text_segments_per_page", type number},
            {"tables_per_page", type number},
            {"table_cells_per_page", type number},
            {"images_per_page", type number},
            {"text_segment_ratio", type number},
            {"image_ratio", type number},
            {"table_ratio", type number}
        }
    )
in
    Typed
