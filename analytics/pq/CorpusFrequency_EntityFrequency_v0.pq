let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\corpus_frequency_v0_18_n2\entity_frequency_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"section_df", Int64.Type},
            {"section_document_count", Int64.Type},
            {"section_df_ratio", type number},
            {"section_idf", type number},
            {"global_df", Int64.Type},
            {"global_document_count", Int64.Type},
            {"global_df_ratio", type number},
            {"global_idf", type number},
            {"occurrence_count", Int64.Type}
        }
    )
in
    Typed
