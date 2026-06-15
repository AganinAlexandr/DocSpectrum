let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_18_n2\axis_b_correlations_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"n", Int64.Type},
            {"spearman", type number},
            {"abs_spearman", type number}
        }
    )
in
    Typed
