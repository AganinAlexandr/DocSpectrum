let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_35_n2\axis_b_correlations_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"n", Int64.Type},
            {"spearman", type number},
            {"abs_spearman", type number},
            {"p_value_approx", type number},
            {"bh_q_value", type number},
            {"partial_n", Int64.Type},
            {"partial_spearman_page_count", type number},
            {"abs_partial_spearman_page_count", type number},
            {"partial_delta_abs", type number}
        }
    )
in
    Typed
