let
    Source = fxLoadCsv(pDocSpectrumRoot & "\analytics\tables\project_events.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"event_date", type date},
            {"event_order", Int64.Type}
        }
    ),
    Sorted = Table.Sort(Typed, {{"event_date", Order.Ascending}, {"event_order", Order.Ascending}})
in
    Sorted
