let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\object_registry_v0\address_tei_consistency_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"object_count", Int64.Type}
        }
    )
in
    Typed
