let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\corpus_frequency_v0_18_n2\section_typicality_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"entity_kind_status", type text},
            {"occurrence_count", Int64.Type},
            {"unique_entity_count", Int64.Type},
            {"typical_occurrences", Int64.Type},
            {"shared_rare_occurrences", Int64.Type},
            {"original_occurrences", Int64.Type},
            {"low_population_occurrences", Int64.Type},
            {"typical_share", type number},
            {"shared_rare_share", type number},
            {"original_share", type number},
            {"low_population_share", type number},
            {"mean_section_idf", type number}
        }
    )
in
    Typed
