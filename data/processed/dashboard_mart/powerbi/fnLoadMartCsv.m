// Crear el parámetro pMartFolder con la ruta a dashboard_mart.
// Luego crear una consulta por archivo: = fnLoadMartCsv("dim_barrio.csv")
(fileName as text) as table =>
let
    Source = Csv.Document(
        File.Contents(pMartFolder & "\" & fileName),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Headers
