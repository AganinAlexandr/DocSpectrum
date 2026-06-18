let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\provenance_assessment_v0\page_provenance_review_sample_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"sample_rank", Int64.Type},
            {"sample_structure_text_ratio", type number},
            {"near_match_similarity_v0", type number},
            {"text_segment_jaccard", type number},
            {"shared_text_segment_count", Int64.Type},
            {"rare_shared_text_segment_count", Int64.Type},
            {"shared_table_layout_count", Int64.Type},
            {"shared_table_content_count", Int64.Type},
            {"left_page_number", Int64.Type},
            {"right_page_number", Int64.Type}
        }
    )
in
    Typed
