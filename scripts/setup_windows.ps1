param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Copy-EnvIfMissing {
    param(
        [string]$Source,
        [string]$Target
    )
    if (-not (Test-Path $Target)) {
        Copy-Item $Source $Target
        Write-Host "created $Target"
    } else {
        Write-Host "exists  $Target"
    }
}

Set-Location $Root

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found, installing with pip..."
    py -m pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple
}

Copy-EnvIfMissing "$Root\backend\.env.example" "$Root\backend\.env"
Copy-EnvIfMissing "$Root\DjangoUserService\.env.example" "$Root\DjangoUserService\.env"

Write-Host "sync backend dependencies..."
Set-Location "$Root\backend"
uv sync --python 3.11

Write-Host "sync user service dependencies..."
Set-Location "$Root\DjangoUserService"
uv sync --python 3.11
New-Item -ItemType Directory -Force "$Root\DjangoUserService\data" | Out-Null
.\.venv\Scripts\python.exe manage.py migrate

if (-not $SkipFrontend) {
    Write-Host "install frontend dependencies..."
    Set-Location "$Root\front"
    if (Test-Path package-lock.json) {
        npm.cmd ci
    } else {
        npm.cmd install
    }
}

Set-Location $Root
Write-Host ""
Write-Host "setup done."
Write-Host "Set DASHSCOPE_API_KEY in Windows environment variables before asking questions."
Write-Host "Then run: powershell -ExecutionPolicy Bypass -File scripts\start_all_windows.ps1"
