$ErrorActionPreference = "Stop"

$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$value = Get-ItemProperty -Path $runKey -Name "WorkdayClock" -ErrorAction SilentlyContinue

if ($null -eq $value) {
  Write-Host "Workday Clock startup entry is not installed."
  exit 0
}

Remove-ItemProperty -Path $runKey -Name "WorkdayClock"
Write-Host "Workday Clock startup entry removed."
