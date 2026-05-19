param(
    [int]$BackendPort = 8010,
    [int]$UserPort = 8011,
    [int]$FrontPort = 3010
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force $Logs | Out-Null

function Start-ProjectProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $OutFile = Join-Path $Logs "$Name.out.log"
    $ErrFile = Join-Path $Logs "$Name.err.log"
    Write-Host "starting $Name..."
    Start-Process powershell `
        -WindowStyle Hidden `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command `
        -RedirectStandardOutput $OutFile `
        -RedirectStandardError $ErrFile | Out-Null
}

Start-ProjectProcess `
    -Name "django-user-service" `
    -WorkingDirectory "$Root\DjangoUserService" `
    -Command ".\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:$UserPort --noreload"

Start-Sleep -Seconds 2

Start-ProjectProcess `
    -Name "fastapi-rag-service" `
    -WorkingDirectory "$Root\backend" `
    -Command ".\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port $BackendPort"

Start-Sleep -Seconds 2

Start-ProjectProcess `
    -Name "vue-frontend" `
    -WorkingDirectory "$Root\front" `
    -Command "`$env:VITE_BACKEND_TARGET='http://127.0.0.1:$BackendPort'; `$env:VITE_USER_SERVICE_TARGET='http://127.0.0.1:$UserPort'; npm.cmd run dev -- --host 127.0.0.1 --port $FrontPort"

Write-Host ""
Write-Host "services started:"
Write-Host "frontend:      http://127.0.0.1:$FrontPort/"
Write-Host "FastAPI docs:  http://127.0.0.1:$BackendPort/docs"
Write-Host "Django users:  http://127.0.0.1:$UserPort"
Write-Host "logs:          $Logs"
