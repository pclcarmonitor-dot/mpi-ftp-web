"""
MPI FTP Web Portal
เว็บสำหรับเข้า FTP/SFTP Server (เช่น jct.fortidyndns.com) ผ่าน Browser
รองรับ: ล็อกอิน, เปิดโฟลเดอร์, ดาวน์โหลด, อัปโหลด, ดูตัวอย่าง CSV / PDF
"""
import io
import os
import csv
import uuid
import posixpath
import ftplib
import stat as statmod
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, send_file, flash, abort, Response)

# ---------- Config (.env) ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FTP_HOST = os.getenv("FTP_HOST", "jct.fortidyndns.com")
FTP_PORT = int(os.getenv("FTP_PORT", "0"))           # 0 = ค่าเริ่มต้นตาม protocol
FTP_PROTOCOL = os.getenv("FTP_PROTOCOL", "sftp").lower()   # sftp | ftp | ftps
FTP_DEFAULT_USER = os.getenv("FTP_DEFAULT_USER", "Mpi")
START_DIR = os.getenv("FTP_START_DIR", "/PO")
ALLOW_UPLOAD = os.getenv("ALLOW_UPLOAD", "true").lower() == "true"
ALLOW_DELETE = os.getenv("ALLOW_DELETE", "false").lower() == "true"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB (ขีดจำกัด Cloudflare free)

# อยู่หลัง Cloudflare Tunnel -> เชื่อ header X-Forwarded-* 1 ชั้น และใช้ cookie แบบปลอดภัย
if os.getenv("BEHIND_PROXY", "false").lower() == "true":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax")

# เก็บรหัสผ่านไว้ฝั่ง server เท่านั้น (ไม่ใส่ใน cookie)
_CREDS = {}


# ---------- Connection layer ----------
class Remote:
    """Wrapper เดียวกันสำหรับ SFTP / FTP / FTPS"""

    def __init__(self, user, password):
        self.proto = FTP_PROTOCOL
        if self.proto == "sftp":
            import paramiko
            port = FTP_PORT or 22
            self.transport = paramiko.Transport((FTP_HOST, port))
            self.transport.connect(username=user, password=password)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        else:
            port = FTP_PORT or 21
            self.ftp = ftplib.FTP_TLS() if self.proto == "ftps" else ftplib.FTP()
            self.ftp.encoding = "utf-8"
            self.ftp.connect(FTP_HOST, port, timeout=30)
            self.ftp.login(user, password)
            if self.proto == "ftps":
                self.ftp.prot_p()
            self.ftp.set_pasv(True)

    def close(self):
        try:
            if self.proto == "sftp":
                self.sftp.close(); self.transport.close()
            else:
                self.ftp.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def listdir(self, path):
        items = []
        if self.proto == "sftp":
            for a in self.sftp.listdir_attr(path):
                items.append({
                    "name": a.filename,
                    "is_dir": statmod.S_ISDIR(a.st_mode or 0),
                    "size": a.st_size or 0,
                    "mtime": datetime.fromtimestamp(a.st_mtime) if a.st_mtime else None,
                })
        else:
            try:
                for name, facts in self.ftp.mlsd(path, facts=["type", "size", "modify"]):
                    if name in (".", ".."):
                        continue
                    t = facts.get("type", "file")
                    if t in ("cdir", "pdir"):
                        continue
                    m = facts.get("modify")
                    items.append({
                        "name": name,
                        "is_dir": t == "dir",
                        "size": int(facts.get("size", 0) or 0),
                        "mtime": datetime.strptime(m[:14], "%Y%m%d%H%M%S") if m else None,
                    })
            except ftplib.error_perm:
                # Server ไม่รองรับ MLSD -> ใช้ NLST + ตรวจทีละรายการ
                cur = self.ftp.pwd()
                for full in self.ftp.nlst(path):
                    name = posixpath.basename(full)
                    if name in (".", ".."):
                        continue
                    is_dir = False
                    try:
                        self.ftp.cwd(posixpath.join(path, name)); is_dir = True
                    except ftplib.error_perm:
                        pass
                    finally:
                        self.ftp.cwd(cur)
                    size = 0
                    if not is_dir:
                        try:
                            size = self.ftp.size(posixpath.join(path, name)) or 0
                        except Exception:
                            pass
                    items.append({"name": name, "is_dir": is_dir, "size": size, "mtime": None})
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return items

    def read(self, path):
        buf = io.BytesIO()
        if self.proto == "sftp":
            self.sftp.getfo(path, buf)
        else:
            self.ftp.retrbinary(f"RETR {path}", buf.write)
        buf.seek(0)
        return buf

    def write(self, path, fileobj):
        if self.proto == "sftp":
            self.sftp.putfo(fileobj, path)
        else:
            self.ftp.storbinary(f"STOR {path}", fileobj)

    def delete(self, path):
        if self.proto == "sftp":
            self.sftp.remove(path)
        else:
            self.ftp.delete(path)


def connect():
    sid = session.get("sid")
    cred = _CREDS.get(sid)
    if not cred:
        abort(401)
    return Remote(cred["user"], cred["password"])


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("sid") not in _CREDS:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def clean_path(p):
    p = posixpath.normpath("/" + (p or "/").lstrip("/"))
    return "/" if p in (".", "") else p


# ---------- Helpers for templates ----------
@app.template_filter("filesize")
def filesize(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@app.context_processor
def inject():
    return {"host": FTP_HOST, "proto": FTP_PROTOCOL.upper(),
            "user": _CREDS.get(session.get("sid"), {}).get("user"),
            "allow_upload": ALLOW_UPLOAD, "allow_delete": ALLOW_DELETE}


# ---------- Routes ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        try:
            r = Remote(user, pw); r.close()
        except Exception as e:
            flash(f"เชื่อมต่อไม่สำเร็จ: {e}", "error")
            return render_template("login.html", default_user=user)
        sid = uuid.uuid4().hex
        _CREDS[sid] = {"user": user, "password": pw}
        session["sid"] = sid
        return redirect(url_for("browse", path=START_DIR))
    return render_template("login.html", default_user=FTP_DEFAULT_USER)


@app.route("/logout")
def logout():
    _CREDS.pop(session.pop("sid", None), None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("browse", path=START_DIR))


@app.route("/browse")
@login_required
def browse():
    path = clean_path(request.args.get("path", START_DIR))
    q = request.args.get("q", "").strip().lower()
    try:
        with connect() as r:
            items = r.listdir(path)
    except Exception as e:
        flash(f"เปิดโฟลเดอร์ {path} ไม่ได้: {e}", "error")
        items = []
    if q:
        items = [i for i in items if q in i["name"].lower()]
    parts, acc = [], ""
    for seg in [s for s in path.split("/") if s]:
        acc += "/" + seg
        parts.append((seg, acc))
    parent = posixpath.dirname(path) if path != "/" else None
    return render_template("browse.html", path=path, items=items, parts=parts,
                           parent=parent, q=q, join=posixpath.join)


@app.route("/download")
@login_required
def download():
    path = clean_path(request.args.get("path"))
    inline = request.args.get("inline") == "1"
    with connect() as r:
        data = r.read(path)
    return send_file(data, download_name=posixpath.basename(path),
                     as_attachment=not inline)


@app.route("/preview")
@login_required
def preview():
    path = clean_path(request.args.get("path"))
    name = posixpath.basename(path)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "pdf":
        return render_template("preview.html", path=path, name=name, kind="pdf")
    if ext in ("csv", "txt"):
        with connect() as r:
            raw = r.read(path).read()
        for enc in ("utf-8-sig", "cp874", "latin-1"):
            try:
                text = raw.decode(enc); break
            except UnicodeDecodeError:
                continue
        rows = list(csv.reader(io.StringIO(text)))[:1000] if ext == "csv" else None
        return render_template("preview.html", path=path, name=name, kind=ext,
                               rows=rows, text=text[:200000])
    return redirect(url_for("download", path=path))


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if not ALLOW_UPLOAD:
        abort(403)
    path = clean_path(request.form.get("path"))
    files = request.files.getlist("files")
    ok = 0
    with connect() as r:
        for f in files:
            if not f.filename:
                continue
            name = posixpath.basename(f.filename.replace("\\", "/"))
            try:
                r.write(posixpath.join(path, name), f.stream); ok += 1
            except Exception as e:
                flash(f"อัปโหลด {name} ไม่สำเร็จ: {e}", "error")
    if ok:
        flash(f"อัปโหลดสำเร็จ {ok} ไฟล์", "ok")
    return redirect(url_for("browse", path=path))


@app.route("/delete", methods=["POST"])
@login_required
def delete():
    if not ALLOW_DELETE:
        abort(403)
    path = clean_path(request.form.get("path"))
    with connect() as r:
        try:
            r.delete(path); flash(f"ลบ {posixpath.basename(path)} แล้ว", "ok")
        except Exception as e:
            flash(f"ลบไม่สำเร็จ: {e}", "error")
    return redirect(url_for("browse", path=posixpath.dirname(path)))


@app.errorhandler(401)
def unauth(_):
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8080")))
