param(
    [int]$TargetTotal = 100000,
    [int]$BatchSize = 10,
    [int]$Concurrency = 1
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$InputDir = Join-Path $Root "docs\rag_test_corpus\split_100k"

Write-Host "This optional script imports the Markdown corpus into Chroma."
Write-Host "It calls the embedding API and may cost money."
Write-Host "The app can already answer from the built-in Markdown corpus without running this script."
Write-Host ""

Set-Location $Root
& "$Root\backend\.venv\Scripts\python.exe" "$Root\tools\import_medical_cards_to_chroma.py" `
    --input $InputDir `
    --user-id "agYcn9m9kHM9AHaHMEcRby" `
    --corpus-name "medical_rag_cards_100000.md" `
    --batch-size $BatchSize `
    --concurrency $Concurrency `
    --target-total $TargetTotal
