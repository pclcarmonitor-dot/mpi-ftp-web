@echo off
REM Cloudflare Quick Tunnel (test only) - URL *.trycloudflare.com changes on every restart
REM Requires the web app running on http://localhost:8080 (install_windows_service.ps1)
set "CF=cloudflared"
where cloudflared >nul 2>nul || (
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
  set "CF=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
)
echo.
echo Look for the line  https://xxxx.trycloudflare.com  below - that is your public URL.
echo Keep this window open. Close it to stop public access.
echo.
"%CF%" tunnel --url http://localhost:8080
pause
