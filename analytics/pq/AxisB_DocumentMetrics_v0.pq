let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_18_n2\axis_b_document_metrics_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"tei_norm_building_volume_m3", type number},
            {"tei_norm_floors_count", type number},
            {"tei_norm_height_m", type number},
            {"tei_norm_apartments_count", type number},
            {"tei_norm_total_area_m2", type number},
            {"tei_norm_footprint_area_m2", type number},
            {"page_count", Int64.Type},
            {"element_count", Int64.Type},
            {"visible_element_count", Int64.Type},
            {"text_segment_count", Int64.Type},
            {"table_count", Int64.Type},
            {"table_cell_count", Int64.Type},
            {"image_count", Int64.Type},
            {"layer_count", Int64.Type},
            {"total_text_chars", Int64.Type},
            {"total_text_words", Int64.Type},
            {"group_text_count", Int64.Type},
            {"group_lines_count", Int64.Type},
            {"group_frames_count", Int64.Type},
            {"group_images_count", Int64.Type},
            {"group_tables_count", Int64.Type},
            {"group_other_vector_count", Int64.Type}
        }
    )
in
    Typed
