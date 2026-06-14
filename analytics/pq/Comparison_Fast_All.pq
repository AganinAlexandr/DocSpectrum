let
    Source = fxLoadCsv(pDocSpectrumSamplesRoot & "\comparison_results_v0\comparison_results_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"weighted_similarity_v0", type number},
            {"feature_cosine_v0", type number},
            {"page_signature_jaccard", type number},
            {"table_layout_jaccard", type number},
            {"table_content_jaccard", type number}
        }
    )
in
    Typed
