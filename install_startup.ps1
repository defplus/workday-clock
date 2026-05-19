$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $projectRoot "start_workday_clock.ps1"
$powershell = (Get-Command powershell.exe).Source
$command = "`"$powershell`" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

Set-ItemProperty -Path $runKey -Name "WorkdayClock" -Value $command
Write-Host "Workday Clock will start when you sign in."
