# -*- coding: utf-8 -*-
"""Folder Launcher - server web kecil untuk menyimpan & membuka folder Windows.

Jalankan: python server.py   (atau double-click start.bat)
Data disimpan dalam paths.json di folder yang sama.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import url2pathname

if os.name == "nt":
    import ctypes
    from ctypes import wintypes
else:
    ctypes = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "paths.json")
PORT = 8765
APP_HEADER = "folder-launcher"
_lock = threading.Lock()


def load_items():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_items(items):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _unwrap_quotes(p):
    while len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
        p = p[1:-1].strip()
    return p


def normalize_path(raw):
    p = _unwrap_quotes(raw.strip())
    if p.lower().startswith("file:///"):
        p = url2pathname(p[7:])
    p = p.replace("/", "\\")
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    return os.path.normpath(p)


_EXPLORER_CLASSES = ("CabinetWClass", "ExploreWClass")


def _explorer_windows():
    user32 = ctypes.windll.user32
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found = []

    def _cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, buf, 64)
            if buf.value in _EXPLORER_CLASSES:
                found.append(hwnd)
        return True

    cb = proto(_cb)
    user32.EnumWindows(cb, 0)
    return found


def _force_foreground(hwnd):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)  # SW_RESTORE / SW_SHOW
    # Lampir ke thread input tetingkap aktif supaya dibenarkan set foreground
    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    this_tid = kernel32.GetCurrentThreadId()
    attached = False
    if fg_tid and fg_tid != this_tid:
        attached = bool(user32.AttachThreadInput(this_tid, fg_tid, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(this_tid, fg_tid, False)
    if user32.GetForegroundWindow() != hwnd:
        user32.SwitchToThisWindow(hwnd, True)  # API taskbar, laluan terakhir


def _launch_explorer(args):
    proc = subprocess.Popen(args)
    if ctypes is None:
        return proc
    try:
        before = set(_explorer_windows())
        hwnd = None
        for _ in range(40):  # tunggu tetingkap baru sehingga ~2 saat
            time.sleep(0.05)
            new = [h for h in _explorer_windows() if h not in before]
            if new:
                hwnd = new[0]
                break
        if hwnd:
            _force_foreground(hwnd)
    except Exception:
        pass  # jika gagal, tetingkap tetap terbuka (tanpa fokus)
    return proc


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_index(self):
        try:
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                body = f.read()
        except OSError:
            return self._send(500, {"error": "index.html tidak dijumpai"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return None

    def _guard(self):
        # Halang permintaan dari website lain (CSRF)
        if self.headers.get("X-App") != APP_HEADER:
            self._send(403, {"error": "Permintaan tidak dibenarkan"})
            return False
        return True

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send_index()
        if self.path == "/api/paths":
            items = load_items()
            for it in items:
                it["exists"] = os.path.isdir(it["path"]) or os.path.isfile(it["path"])
            return self._send(200, items)
        return self._send(404, {"error": "Tiada route"})

    def do_POST(self):
        if not self._guard():
            return
        data = self._read_body()
        if data is None:
            return self._send(400, {"error": "JSON tidak sah"})

        if self.path == "/api/paths":
            raw = str(data.get("path") or "").strip()
            if not raw:
                return self._send(400, {"error": "Path folder diperlukan"})
            p = normalize_path(raw)
            name = str(data.get("name") or "").strip() or (os.path.basename(p.rstrip("\\")) or p)
            with _lock:
                items = load_items()
                for it in items:
                    if it["path"].lower() == p.lower():
                        return self._send(200, dict(it, already=True))
                item = {"id": uuid.uuid4().hex[:8], "name": name, "path": p}
                items.append(item)
                save_items(items)
            return self._send(200, dict(item, already=False))

        if self.path == "/api/open":
            item_id = str(data.get("id") or "")
            p = ""
            if item_id:
                for it in load_items():
                    if it["id"] == item_id:
                        p = it["path"]
                        break
            else:
                p = normalize_path(str(data.get("path") or ""))
            if not p:
                return self._send(400, {"error": "ID atau path diperlukan"})
            try:
                if os.path.isdir(p):
                    _launch_explorer(["explorer.exe", p])
                elif os.path.isfile(p):
                    _launch_explorer(["explorer.exe", "/select," + p])
                else:
                    return self._send(404, {"error": "Folder tidak dijumpai: " + p})
            except OSError as e:
                return self._send(500, {"error": "Gagal buka folder: %s" % e})
            return self._send(200, {"ok": True, "path": p})

        if self.path == "/api/pick":
            return self._pick_dialog()

        return self._send(404, {"error": "Tiada route"})

    def _pick_dialog(self):
        ps_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
            "Add-Type -AssemblyName System.Windows.Forms | Out-Null;"
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$f.Description = 'Pilih folder untuk ditambah ke Folder Launcher';"
            "$owner = New-Object System.Windows.Forms.Form;"
            "$owner.TopMost = $true;"
            "if ($f.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK)"
            "{ Write-Output $f.SelectedPath }"
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=900,
            )
        except FileNotFoundError:
            return self._send(500, {"error": "PowerShell tidak dijumpai"})
        except subprocess.TimeoutExpired:
            return self._send(200, {"path": None})
        path = (out.stdout or "").strip()
        return self._send(200, {"path": path or None})

    def do_DELETE(self):
        if not self._guard():
            return
        m = re.match(r"^/api/paths/([0-9a-fA-F]{4,32})$", self.path)
        if not m:
            return self._send(404, {"error": "Tiada route"})
        with _lock:
            items = load_items()
            remaining = [it for it in items if it["id"] != m.group(1)]
            if len(remaining) == len(items):
                return self._send(404, {"error": "Folder tiada dalam senarai"})
            save_items(remaining)
        return self._send(200, {"ok": True})

    def log_message(self, *args):
        pass  # senyapkan log permintaan


def main():
    url = "http://127.0.0.1:%d" % PORT
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("Port %d sedang digunakan." % PORT)
        print("Mungkin Folder Launcher sudah berjalan - cuba buka %s" % url)
        return
    print("=" * 52)
    print("  Folder Launcher sedang berjalan")
    print("  Buka: %s" % url)
    print("  Data: %s" % DATA_FILE)
    print("  Biarkan tetingkap ini terbuka (Ctrl+C untuk henti)")
    print("=" * 52)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")


if __name__ == "__main__":
    main()
