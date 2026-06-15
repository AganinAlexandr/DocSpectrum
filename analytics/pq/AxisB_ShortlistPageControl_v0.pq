let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_35_n2\axis_b_shortlist_page_control_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"partial_threshold_abs_spearman", type number},
            {"all35_n", Int64.Type},
            {"all35_spearman", type number},
            {"all35_abs_spearman", type number},
            {"all35_bh_q_value", type number},
            {"all35_partial_n", Int64.Type},
            {"all35_partial_spearman_page_count", type number},
            {"all35_abs_partial_spearman_page_count", type number},
            {"partial_delta_abs", type number},
            {"first18_abs_spearman", type number},
            {"added17_abs_spearman", type number}
        }
    )
in
    Typed
