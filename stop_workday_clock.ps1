$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $projectRoot "run_workday_clock.py"

$matches = Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match "python" -and
    $_.CommandLine -like "*$runner*"
  }

if (-not $matches) {
  Write-Host "Workday Clock is not running."
  exit 0
}

foreach ($process in $matches) {
  Stop-Process -Id $process.ProcessId -Force
  Write-Host "Stopped Workday Clock process $($process.ProcessId)."
}
