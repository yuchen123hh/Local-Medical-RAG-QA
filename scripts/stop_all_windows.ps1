param(
    [int[]]$Ports = @(8010, 8011, 3010)
)

$ErrorActionPreference = "SilentlyContinue"

foreach ($Port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen
    foreach ($connection in $connections) {
        $pidToStop = $connection.OwningProcess
        if ($pidToStop) {
            Write-Host "stopping port $Port pid $pidToStop"
            Stop-Process -Id $pidToStop -Force
        }
    }
}

Write-Host "done."
