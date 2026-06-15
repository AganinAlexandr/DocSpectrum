let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\corpus_frequency_v0_35_n2\section_library_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"page_count", Int64.Type},
            {"text_segment_count", Int64.Type},
            {"total_text_chars", Int64.Type},
            {"total_text_words", Int64.Type},
            {"broken_encoding_count", Int64.Type}
        }
    )
in
    Typed
