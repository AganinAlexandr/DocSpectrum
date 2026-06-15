let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\eval_set_v0_18_n2\eval_pair_labels_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"same_address", type logical},
            {"same_address_cross_system", type logical},
            {"tei_distance_z", type number},
            {"tei_distance_field_count", Int64.Type},
            {"expected_similarity_rank", Int64.Type},
            {"idf_similarity_v0_3", type number},
            {"combined_similarity_v0_2", type number},
            {"section_percentile_v0_3", type number},
            {"page_signature_idf_jaccard", type number}
        }
    )
in
    Typed
