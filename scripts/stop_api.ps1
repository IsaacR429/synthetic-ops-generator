$ErrorActionPreference = "Stop"

$ApiModule = "synthetic_ops_generator.api.app:app"
$Port = 8000

Write-Host "Checking Synthetic Operational Data Generator API..."

$apiProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match [regex]::Escape($ApiModule) -and
        $_.CommandLine -match "uvicorn"
    }

if ($apiProcesses) {
    foreach ($process in $apiProcesses) {
        Write-Host "Stopping API process PID $($process.ProcessId)..."

        Stop-Process `
            -Id $process.ProcessId `
            -Force `
            -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 1
}
else {
    Write-Host "No Synthetic Operational Data Generator API process found."
}

$listener = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($listener) {
    Write-Warning (
        "Port $Port is still occupied by PID " +
        $listener.OwningProcess +
        ". It was not killed because it was not identified " +
        "as this project's API."
    )

    exit 1
}

Write-Host "API stopped. Port $Port is free."
