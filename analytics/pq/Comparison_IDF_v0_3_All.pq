let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\comparison_results_v0_3_18_n2\comparison_results_v0_3.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"idf_similarity_v0_3", type number},
            {"idf_applicable_weight", type number},
            {"combined_similarity_v0_2", type number},
            {"text_similarity_v0_2", type number},
            {"signature_similarity_v0_1", type number},
            {"page_signature_idf_jaccard", type number},
            {"text_segment_idf_jaccard", type number},
            {"text_segment_raw_jaccard", type number},
            {"text_segment_shared_unique", Int64.Type},
            {"text_word_shingle_idf_jaccard", type number},
            {"text_word_shingle_raw_jaccard", type number},
            {"text_word_shingle_shared_unique", Int64.Type},
            {"table_cell_text_idf_jaccard", type number},
            {"table_cell_text_raw_jaccard", type number},
            {"table_cell_text_shared_unique", Int64.Type},
            {"table_layout_signature_idf_jaccard", type number},
            {"table_layout_signature_raw_jaccard", type number},
            {"table_layout_signature_shared_unique", Int64.Type},
            {"table_content_signature_idf_jaccard", type number},
            {"table_content_signature_raw_jaccard", type number},
            {"table_content_signature_shared_unique", Int64.Type}
        }
    )
in
    Typed
