let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_18_n2\axis_b_tei_bucket_summary_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"document_count", Int64.Type},
            {"bucket_low_threshold", type number},
            {"bucket_high_threshold", type number},
            {"median_page_count", type number},
            {"median_element_count", type number},
            {"median_table_count", type number},
            {"median_table_cell_count", type number},
            {"median_total_text_words", type number},
            {"median_group_lines_count", type number},
            {"median_group_frames_count", type number},
            {"median_group_tables_count", type number}
        }
    )
in
    Typed
