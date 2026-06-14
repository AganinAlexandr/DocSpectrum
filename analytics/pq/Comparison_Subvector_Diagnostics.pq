let
    Source = Comparison_Detailed_All,
    Keep = Table.SelectColumns(
        Source,
        {
            "pair_id",
            "section_code",
            "feature_cosine_v0",
            "subvector_volume_cosine",
            "subvector_volume_centered_cosine",
            "subvector_density_cosine",
            "subvector_density_centered_cosine",
            "subvector_text_cosine",
            "subvector_text_centered_cosine",
            "subvector_tables_cosine",
            "subvector_tables_centered_cosine",
            "subvector_graphics_cosine",
            "subvector_graphics_centered_cosine",
            "subvector_element_mix_cosine",
            "subvector_element_mix_centered_cosine"
        }
    ),
    Unpivoted = Table.UnpivotOtherColumns(
        Keep,
        {"pair_id", "section_code", "feature_cosine_v0"},
        "metric",
        "value"
    ),
    WithKind = Table.AddColumn(
        Unpivoted,
        "cosine_kind",
        each if Text.Contains([metric], "_centered_") then "centered" else "raw",
        type text
    ),
    WithSubvector = Table.AddColumn(
        WithKind,
        "subvector",
        each
            Text.Replace(
                Text.Replace(
                    Text.Replace([metric], "subvector_", ""),
                    "_centered_cosine",
                    ""
                ),
                "_cosine",
                ""
            ),
        type text
    ),
    Selected = Table.SelectColumns(
        WithSubvector,
        {"pair_id", "section_code", "subvector", "cosine_kind", "value", "feature_cosine_v0"}
    )
in
    Selected
