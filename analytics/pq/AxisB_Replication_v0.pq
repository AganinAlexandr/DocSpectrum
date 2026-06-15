let
    Source = fxLoadCsv(pDocSpectrumOutputRoot & "\axis_b_correlations_v0_35_n2\axis_b_replication_v0.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"replication_threshold_abs_spearman", type number},
            {"first18_n", Int64.Type},
            {"first18_spearman", type number},
            {"first18_abs_spearman", type number},
            {"first18_bh_q_value", type number},
            {"added17_n", Int64.Type},
            {"added17_spearman", type number},
            {"added17_abs_spearman", type number},
            {"added17_bh_q_value", type number},
            {"all35_n", Int64.Type},
            {"all35_spearman", type number},
            {"all35_abs_spearman", type number},
            {"all35_bh_q_value", type number},
            {"all35_partial_spearman_page_count", type number},
            {"all35_abs_partial_spearman_page_count", type number}
        }
    )
in
    Typed
