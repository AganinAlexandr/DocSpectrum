let
    Source = fxLoadCsv(pDocSpectrumSamplesRoot & "\element_base_v0\documents_index.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"page_count", Int64.Type},
            {"element_count", Int64.Type},
            {"text_segment_count", Int64.Type},
            {"table_count", Int64.Type},
            {"table_cell_count", Int64.Type},
            {"image_count", Int64.Type}
        }
    )
in
    Typed
