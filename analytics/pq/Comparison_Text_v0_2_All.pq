let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\comparison_results_v0_2_35_n2\comparison_results_v0_2.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"combined_similarity_v0_2", type number},
            {"signature_similarity_v0_1", type number},
            {"text_similarity_v0_2", type number},
            {"text_segment_hash_jaccard", type number},
            {"text_word_shingle_jaccard", type number},
            {"feature_cosine_v0", type number},
            {"left_text_segment_count", Int64.Type},
            {"right_text_segment_count", Int64.Type},
            {"left_text_token_count", Int64.Type},
            {"right_text_token_count", Int64.Type},
            {"left_word_shingle_count", Int64.Type},
            {"right_word_shingle_count", Int64.Type}
        }
    )
in
    Typed
