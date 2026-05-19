$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$runner = Join-Path $projectRoot "run_workday_clock.py"

$existing = Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match "python" -and
    $_.CommandLine -like "*$runner*"
  }

if ($existing) {
  Write-Host "Workday Clock is already running."
  exit 0
}

Start-Process `
  -FilePath $python `
  -ArgumentList @("-B", $runner) `
  -WorkingDirectory $projectRoot `
  -WindowStyle Hidden

Write-Host "Workday Clock started."
