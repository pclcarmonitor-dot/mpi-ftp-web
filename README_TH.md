# MPI FTP Web Portal

เว็บสำหรับเข้า FTP Server `jct.fortidyndns.com` (user `Mpi`) ผ่าน Browser แทน WinSCP

## ความสามารถ
- ล็อกอินด้วย username/password ของ FTP (รหัสผ่านเก็บฝั่ง server เท่านั้น ไม่เก็บใน cookie)
- เปิดดูโฟลเดอร์ เริ่มที่ `/PO` (มี PDF, CSV)
- ค้นหาชื่อไฟล์, ดาวน์โหลด, อัปโหลดหลายไฟล์
- ดูตัวอย่าง PDF ในหน้าเว็บ และเปิด CSV เป็นตาราง (รองรับภาษาไทย UTF-8 / TIS-620)
- ปุ่มลบไฟล์ (ปิดไว้เป็นค่าเริ่มต้น เปิดได้ด้วย `ALLOW_DELETE=true`)
- รองรับ SFTP, FTP, FTPS

## ติดตั้งบน Windows (ง่ายที่สุด)
1. ติดตั้ง Python 3.10+ (ติ๊ก "Add to PATH")
2. แตกไฟล์ zip แล้วดับเบิลคลิก `run_windows.bat`
3. แก้ไฟล์ `.env` ให้ `FTP_PROTOCOL` ตรงกับ WinSCP (Session > File protocol) แล้วรันใหม่
4. เปิด http://localhost:8080 — คนอื่นในวงแลนเข้าได้ที่ `http://<IP เครื่องนี้>:8080`

## ติดตั้งบน Linux
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # แล้วแก้ค่า
waitress-serve --port=8080 app:app
```

## ใช้งานนอกบริษัท (Cloudflare)
ดู [deploy/CLOUDFLARE_TH.md](deploy/CLOUDFLARE_TH.md) — ติดตั้งเป็นบริการบน Windows + Cloudflare Tunnel + Access

## ความปลอดภัย
- ถ้าจะเปิดให้เข้าจากอินเทอร์เน็ต ควรวางหลัง HTTPS (เช่น FortiGate / Nginx / IIS reverse proxy)
- ตั้ง `SECRET_KEY` เป็นข้อความสุ่มยาว ๆ
