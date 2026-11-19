# ติดตั้ง MPI FTP Web ให้รันอัตโนมัติตอนเปิดเครื่อง (Windows)
# วิธีใช้: คลิกขวา PowerShell > Run as Administrator แล้วรัน
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\deploy\install_windows_service.ps1
$ErrorActionPreference = "Stop"
$App = Split-Path -Parent $PSScriptRoot
Set-Location $App

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\pip.exe install -r requirements.txt -q
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    $key = -join ((48..57)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
    (Get-Content .env) -replace 'SECRET_KEY=.*', "SECRET_KEY=$key" `
                       -replace 'BEHIND_PROXY=.*', 'BEHIND_PROXY=true' `
                       -replace 'HOST=0.0.0.0', 'HOST=127.0.0.1' | Set-Content .env
    Write-Host "สร้าง .env แล้ว - ตรวจ FTP_PROTOCOL ใน .env ให้ตรงกับ WinSCP" -ForegroundColor Yellow
}

$exe  = Join-Path $App ".venv\Scripts\waitress-serve.exe"
$act  = New-ScheduledTaskAction -Execute $exe -Argument "--listen=127.0.0.1:8080 app:app" -WorkingDirectory $App
$trig = New-ScheduledTaskTrigger -AtStartup
$set  = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "MPI-FTP-Web" -Action $act -Trigger $trig -Settings $set `
    -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName "MPI-FTP-Web"
Start-Sleep 3
try { Invoke-WebRequest http://127.0.0.1:8080/login -UseBasicParsing | Out-Null
      Write-Host "OK: เว็บทำงานที่ http://127.0.0.1:8080" -ForegroundColor Green }
catch { Write-Host "เว็บยังไม่ตอบ - ตรวจ Task Scheduler > MPI-FTP-Web" -ForegroundColor Red }
