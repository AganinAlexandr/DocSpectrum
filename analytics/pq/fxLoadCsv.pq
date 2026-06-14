(filePath as text) as table =>
let
    Source = Csv.Document(
        File.Contents(filePath),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted
