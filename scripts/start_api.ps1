$ErrorActionPreference = "Stop"

$Port = 8000
$HostAddress = "127.0.0.1"
$ApiModule = "synthetic_ops_generator.api.app:app"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

$listener = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($listener) {
    $ownerPid = $listener.OwningProcess

    $owner = Get-CimInstance Win32_Process `
        -Filter "ProcessId = $ownerPid" `
        -ErrorAction SilentlyContinue

    if (
        $owner -and
        $owner.CommandLine -match [regex]::Escape($ApiModule)
    ) {
        Write-Host (
            "Synthetic Operational Data Generator API " +
            "is already running on port $Port " +
            "(PID $ownerPid)."
        )

        exit 0
    }

    Write-Error (
        "Port $Port is already occupied by another process " +
        "(PID $ownerPid). The API was not started."
    )

    exit 1
}

$PythonExe = & py -3.13 -c "import sys; print(sys.executable)"

if (-not $PythonExe) {
    Write-Error "Python 3.13 could not be resolved."
    exit 1
}

Write-Host "Starting Synthetic Operational Data Generator Control API..."
Write-Host "Python: $PythonExe"
Write-Host "Address: http://${HostAddress}:$Port"
Write-Host "Swagger: http://${HostAddress}:$Port/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop the API."
Write-Host ""

& $PythonExe `
    -m uvicorn `
    $ApiModule `
    --host $HostAddress `
    --port $Port
