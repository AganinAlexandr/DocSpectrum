let
    Source = fxLoadCsv(pDocSpectrumSamplesRoot & "\element_base_v0\corpus_signatures_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"occurrence_count", Int64.Type},
            {"document_count", Int64.Type},
            {"object_count", Int64.Type}
        }
    )
in
    Typed
