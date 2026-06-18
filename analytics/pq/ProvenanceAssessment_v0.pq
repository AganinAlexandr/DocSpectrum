let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\provenance_assessment_v0\page_provenance_assessment_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"review_rank", Int64.Type},
            {"near_match_similarity_v0", type number},
            {"text_segment_jaccard", type number},
            {"shared_text_segment_count", Int64.Type},
            {"rare_shared_text_segment_count", Int64.Type},
            {"shared_text_global_idf_sum", type number},
            {"max_shared_text_global_idf", type number},
            {"table_layout_jaccard", type number},
            {"shared_table_layout_count", Int64.Type},
            {"table_content_jaccard", type number},
            {"shared_table_content_count", Int64.Type},
            {"left_page_number", Int64.Type},
            {"right_page_number", Int64.Type}
        }
    )
in
    Typed
