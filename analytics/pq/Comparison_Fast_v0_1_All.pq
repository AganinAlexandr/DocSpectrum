let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\comparison_results_v0_1_18_n2\comparison_results_v0_1.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"signature_similarity_v0_1", type number},
            {"feature_cosine_v0", type number},
            {"page_signature_jaccard", type number},
            {"table_layout_jaccard", type number},
            {"table_content_jaccard", type number},
            {"scoring_axes_applicable_weight", type number}
        }
    )
in
    Typed
