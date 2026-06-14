let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\object_registry_v0\object_registry_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"tei_count", Int64.Type}
        }
    )
in
    Typed
