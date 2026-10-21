# Fills in the contents, the lists of figures and tables and the page numbers of the report built by
# build_report.py, then saves the .docx and exports the PDF (with bookmarks for every heading).
#
#   powershell -ExecutionPolicy Bypass -File docs/report/export_report.ps1

param([string]$Docx = (Join-Path $PSScriptRoot "Breathe_India_report.docx"))

$ErrorActionPreference = "Stop"
$Docx = (Resolve-Path $Docx).Path
$Pdf = [IO.Path]::ChangeExtension($Docx, ".pdf")

$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($Docx)
    # Contents entries for the main sections in bold, as in the MPSTME report format
    $toc1 = $doc.Styles.Item(-20)                  # wdStyleTOC1
    $toc1.Font.Bold = $true
    $toc1.ParagraphFormat.SpaceBefore = 3
    # Twice: filling in the lists can move headings to a later page
    foreach ($pass in 1..2) {
        foreach ($t in $doc.TablesOfContents) { $t.Update() | Out-Null }
        foreach ($t in $doc.TablesOfFigures) { $t.Update() | Out-Null }
        $doc.Fields.Update() | Out-Null
    }
    $doc.Save()
    # ExportAsFixedFormat(path, wdExportFormatPDF, open, optimise, range, from, to, item, docProps, IRM, headingBookmarks)
    $doc.ExportAsFixedFormat($Pdf, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
    "pages: " + $doc.ComputeStatistics(2)
    $doc.Close()
}
finally {
    $word.Quit()
}
"Saved $Docx"
"Saved $Pdf"
