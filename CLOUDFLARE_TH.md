# เปิดใช้งานนอกบริษัทด้วย Cloudflare Tunnel + Access (Windows)

```
ผู้ใช้ (นอกบริษัท) ──HTTPS──> Cloudflare (Access: ยืนยันอีเมล)
                                   │  Tunnel (ไม่ต้องเปิด port ที่ firewall)
                                   ▼
             Windows ในบริษัท: cloudflared ──> MPI FTP Web :8080 ──> jct.fortidyndns.com
```

## 1. ติดตั้งเว็บบนเครื่อง Windows (เครื่องที่เปิด 24 ชม.)
1. ติดตั้ง Python 3.10+ (ติ๊ก Add to PATH) และ Git
2. `git clone https://github.com/<user>/mpi-ftp-web.git C:\mpi-ftp-web`
3. เปิด PowerShell แบบ Administrator:
   ```powershell
   cd C:\mpi-ftp-web
   Set-ExecutionPolicy -Scope Process Bypass
   .\deploy\install_windows_service.ps1
   ```
4. แก้ `C:\mpi-ftp-web\.env` ให้ `FTP_PROTOCOL` ถูกต้อง แล้วสั่ง `Restart-ScheduledTask MPI-FTP-Web`
   (หรือ Stop/Start ใน Task Scheduler)

## 2. สร้าง Cloudflare Tunnel
1. https://one.dash.cloudflare.com → **Networks → Tunnels → Create a tunnel** → เลือก **Cloudflared**
2. ตั้งชื่อ `mpi-ftp-web` → เลือก **Windows** → คัดลอกคำสั่งที่ให้มา แล้วรันใน PowerShell (Admin):
   ```powershell
   cloudflared.exe service install <TOKEN>
   ```
   (ติดตั้ง cloudflared ก่อน: `winget install --id Cloudflare.cloudflared`)
3. แท็บ **Public Hostname**:
   - Subdomain: `ftp` · Domain: โดเมนของคุณ
   - Service: **HTTP** · URL: `localhost:8080`
4. Save → เข้าได้ที่ `https://ftp.<โดเมน>`

## 3. ล็อกให้เฉพาะคนในบริษัท (Cloudflare Access) — แนะนำมาก
1. **Access → Applications → Add an application → Self-hosted**
2. Application domain: `ftp.<โดเมน>`
3. Policy: Action **Allow** · Include → **Emails ending in** `@pharmacarelimited.com`
   (หรือระบุอีเมลรายคน)
4. Login method: **One-time PIN** (ส่งรหัสเข้าอีเมล) หรือ Microsoft Entra ID / Google

ผลลัพธ์: ต้องผ่าน 2 ชั้น — ยืนยันอีเมลกับ Cloudflare แล้วจึงล็อกอิน FTP

## อัปเดตเวอร์ชันใหม่
```powershell
cd C:\mpi-ftp-web; git pull; Restart-ScheduledTask MPI-FTP-Web
```

## หมายเหตุ
- Cloudflare แพ็กเกจฟรี จำกัดขนาดอัปโหลดต่อไฟล์ 100 MB
- ไม่ต้องเปิด port ใด ๆ ที่ FortiGate — cloudflared เชื่อมออกไปหา Cloudflare เอง
