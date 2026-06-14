let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\object_registry_v0\object_tei_long_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"value_number", type number}
        }
    )
in
    Typed
