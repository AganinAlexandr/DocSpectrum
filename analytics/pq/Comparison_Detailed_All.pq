let
    Source = fxLoadCsv(pDocSpectrumSamplesRoot & "\detailed_comparison_results_v0\detailed_comparison_results_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"detailed_similarity_v0", type number},
            {"feature_cosine_v0", type number},
            {"subvector_volume_cosine", type number},
            {"subvector_volume_centered_cosine", type number},
            {"subvector_density_cosine", type number},
            {"subvector_density_centered_cosine", type number},
            {"subvector_text_cosine", type number},
            {"subvector_text_centered_cosine", type number},
            {"subvector_tables_cosine", type number},
            {"subvector_tables_centered_cosine", type number},
            {"subvector_graphics_cosine", type number},
            {"subvector_graphics_centered_cosine", type number},
            {"subvector_element_mix_cosine", type number},
            {"subvector_element_mix_centered_cosine", type number},
            {"page_signature_jaccard", type number},
            {"table_layout_jaccard", type number},
            {"table_content_jaccard", type number},
            {"exact_text_segment_jaccard", type number},
            {"same_page_number_exact_match_count", Int64.Type},
            {"shared_page_signature_count", Int64.Type},
            {"shared_table_layout_signature_count", Int64.Type},
            {"shared_table_content_signature_count", Int64.Type},
            {"shared_text_unique_segment_count", Int64.Type}
        }
    )
in
    Typed
