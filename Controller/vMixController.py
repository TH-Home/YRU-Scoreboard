# -*- coding: utf-8 -*-
"""
vMixController — YRU Stadium Scoreboard Server (Desktop)
=========================================================
Single-file desktop app. Build to vMixController.exe with build-exe.bat.

Responsibilities
  1. HTTP server on :8080
       GET  /                → serves index.html (the mobile web app)
       GET  /config          → current match config (JSON)
       POST /config          → update config (quick edits from phone/iPad)
       GET  /logos/<file>    → serve logo images (for web previews)
  2. Match Setup GUI (dark theme matching the web app):
       - Connection URLs (Server / LAN IP / WiFi IP) with Copy buttons
       - Setup Mode  : Match Mode (Thai League / General), Title Type (Logo / Title)
       - Match Setup : Day / Date / Month / Year / Kick Off, Periods 2–4,
                       minutes per period, Clock Mode
       - Competition & Teams : names, colors, logos (Drag & Drop)
       - Timing      : Countdown duration, Goal! duration
  3. Close / minimize → system tray (bottom-right). Exit via tray menu.

Data lives in C:\\vMixData
  config.json   — all match settings (single source of truth)
  logos\\        — dropped logo files (referenced by filename)
  index.html    — the web app served to phones

Dependencies (see build-exe.bat):
  pip install tkinterdnd2 pystray pillow
"""

import datetime
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
import urllib.request

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

# ── Optional deps (graceful fallback) ────────────────────────────────────────
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    HAS_DND = False

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

try:
    from tkcalendar import DateEntry
    HAS_CAL = True
except Exception:
    HAS_CAL = False

# ═════════════════════════════════════════════════════════════════════════════
# CONSTANTS / PATHS
# ═════════════════════════════════════════════════════════════════════════════
APP_NAME    = "vMixController"
APP_VERSION = "4.7.0"
HTTP_PORT   = 8080
GITHUB_REPO = "TH-Home/YRU-Scoreboard"   # used only for the update check (public repo, no auth needed)

BASE_DIR   = r"C:\vMixData" if os.name == "nt" else os.path.expanduser("~/vMixData")
LOGO_DIR   = os.path.join(BASE_DIR, "logos")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
INDEX_PATH  = os.path.join(BASE_DIR, "index.html")
BACKUP_DIR  = os.path.join(BASE_DIR, "backups")
MATCHLOG_PATH = os.path.join(BASE_DIR, "matches.json")

DEFAULT_CONFIG = {
    # Setup Mode
    "matchMode": "thai",          # thai | general
    "titleType": "logo",          # logo | title
    # Match Setup
    "dayOfWeek": "",
    "date": "",
    "month": "",
    "year": "",
    "kickOff": "15:00",
    "periodCount": 2,             # 2–4
    "periodMins": 45,
    "clockMode": "continuous",    # continuous | reset
    # Competition & Teams
    "compName": "",
    "compLogo": "",               # filename inside logos/
    "homeName": "HOME",
    "homeColor": "#1a3a6b",
    "homeLogo": "",
    "awayName": "AWAY",
    "awayColor": "#8b0000",
    "awayLogo": "",
    # Timing
    "countdownDuration": 7000,    # Thai League only; match clock starts at (dur - 1750ms)
    "goalDuration": 13000,
}

DAYS   = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


# ═════════════════════════════════════════════════════════════════════════════
# UPDATE CHECK (GitHub Releases — public repo, no auth needed to read)
# ═════════════════════════════════════════════════════════════════════════════
def _version_tuple(v):
    parts = []
    for p in v.split("."):
        try: parts.append(int(p))
        except ValueError: parts.append(0)
    return tuple(parts)


def check_for_update(on_found):
    """Runs in a background thread; calls on_found(latest_version, url) if a
    newer GitHub release exists. Fails silently (no internet, rate limit,
    no releases published yet, etc.) since this is a nice-to-have, not core."""
    def worker():
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.load(r)
            latest = str(data.get("tag_name", "")).lstrip("vV")
            url = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
            if latest and _version_tuple(latest) > _version_tuple(APP_VERSION):
                on_found(latest, url)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

# Dark glassmorphism palette — mirrors the web app
C = {
    "bg":        "#0b1220",
    "card":      "#121a2b",
    "card2":     "#0e1524",
    "border":    "#233047",
    "text":      "#e8eefc",
    "text2":     "#9fb0cc",
    "muted":     "#5c6b85",
    "blue":      "#3b9eff",
    "cyan":      "#00d4ff",
    "green":     "#00e676",
    "amber":     "#ffb300",
    "red":       "#ff3d3d",
    "purple":    "#b57bff",
    "input":     "#0a101d",
}

FONT_FAMILY = "Prompt"        # registered at startup via register_fonts(); falls back to a system
                              # default automatically if that fails, so no separate fallback needed
FONT      = (FONT_FAMILY, 10)
FONT_SM   = (FONT_FAMILY, 9)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_H    = (FONT_FAMILY, 11, "bold")
FONT_MONO = ("Consolas", 10)


def register_fonts():
    """Load the bundled Prompt TTFs for this process only (no admin rights,
    no system-wide install needed) so Tkinter can reference the family."""
    if os.name != "nt":
        return
    fonts_dir = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "fonts")
    try:
        from ctypes import windll, create_unicode_buffer
        FR_PRIVATE = 0x10
        for fname in ("Prompt-Regular.ttf", "Prompt-Bold.ttf"):
            path = os.path.join(fonts_dir, fname)
            if os.path.exists(path):
                windll.gdi32.AddFontResourceExW(create_unicode_buffer(path), FR_PRIVATE, 0)
    except Exception:
        pass


def ensure_startup_shortcut():
    """Create a Windows Startup shortcut to this exe on first run, so a fresh
    install auto-starts without anyone manually placing a shortcut in
    shell:startup. Only runs for the built exe (a shortcut to python.exe
    running a .py script wouldn't be useful), and only if none exists yet."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    shortcut_path = os.path.join(startup_dir, f"{APP_NAME}.lnk")
    if os.path.exists(shortcut_path):
        return
    exe_path = sys.executable
    ps_script = (
        "$s = New-Object -ComObject WScript.Shell;"
        f"$sc = $s.CreateShortcut('{shortcut_path}');"
        f"$sc.TargetPath = '{exe_path}';"
        f"$sc.WorkingDirectory = '{os.path.dirname(exe_path)}';"
        "$sc.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG STORE (thread-safe; shared between GUI and HTTP server)
# ═════════════════════════════════════════════════════════════════════════════
class ConfigStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.data = dict(DEFAULT_CONFIG)
        self.dirty_from_http = threading.Event()   # set by HTTP thread; GUI polls it
        self.load()

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            with self._lock:
                for k in DEFAULT_CONFIG:
                    if k in saved:
                        self.data[k] = saved[k]
        except Exception:
            pass  # first run — defaults

    def save(self):
        os.makedirs(BASE_DIR, exist_ok=True)
        with self._lock:
            snap = dict(self.data)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)

    def get(self):
        with self._lock:
            return dict(self.data)

    def update(self, patch, from_http=False):
        with self._lock:
            for k, v in patch.items():
                if k in DEFAULT_CONFIG:
                    self.data[k] = v
        self.save()
        if from_http:
            self.dirty_from_http.set()   # GUI thread polls this — never touch tk from here


CONFIG = ConfigStore()


# ═════════════════════════════════════════════════════════════════════════════
# MATCH LOG (append a record on Start Match, keep its score updated live)
# ═════════════════════════════════════════════════════════════════════════════
class MatchLog:
    def __init__(self):
        self._lock = threading.Lock()

    def _load(self):
        try:
            with open(MATCHLOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, records):
        os.makedirs(BASE_DIR, exist_ok=True)
        tmp = MATCHLOG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        os.replace(tmp, MATCHLOG_PATH)

    def start(self, data):
        with self._lock:
            records = self._load()
            records.append({
                "date": data.get("date", ""),
                "competition": data.get("competition", ""),
                "homeName": data.get("homeName", ""),
                "awayName": data.get("awayName", ""),
                "kickOff": data.get("kickOff", ""),
                "homeScore": 0,
                "awayScore": 0,
                "startedAt": datetime.datetime.now().isoformat(timespec="seconds"),
            })
            self._save(records)

    def update_score(self, home_score, away_score):
        with self._lock:
            records = self._load()
            if not records:
                return
            records[-1]["homeScore"] = home_score
            records[-1]["awayScore"] = away_score
            self._save(records)

    def clock_event(self, event, clock_seconds, period, wall_clock_at):
        """Wall-clock-anchored checkpoint for the match clock, so a computer
        crash/restart can recompute the correct elapsed time afterwards --
        vMix's own Countdown object has no memory of its position once vMix
        itself restarts. 'running' reflects state AFTER this event (a
        'start'/'resume' leaves it running; 'pause'/'reset' stop it)."""
        with self._lock:
            records = self._load()
            if not records:
                return
            record = records[-1]
            record.setdefault("clockEvents", []).append({
                "event": event, "clockSeconds": clock_seconds,
                "period": period, "wallClockAt": wall_clock_at,
            })
            record["lastClockState"] = {
                "running": event in ("start", "resume"),
                "anchorWallClock": wall_clock_at,
                "clockSecondsAtAnchor": clock_seconds,
                "period": period,
            }
            self._save(records)

    def last_clock_state(self):
        with self._lock:
            records = self._load()
        if not records:
            return None
        record = records[-1]
        state = record.get("lastClockState")
        if not state:
            return None
        return dict(state, homeScore=record.get("homeScore", 0), awayScore=record.get("awayScore", 0))


MATCHLOG = MatchLog()


# ═════════════════════════════════════════════════════════════════════════════
# HTTP SERVER
# ═════════════════════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/{APP_VERSION}"

    def log_message(self, *a):  # silence console spam
        pass

    # -- helpers ---------------------------------------------------------------
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, b'{"error":"not found"}')

    # -- routes ----------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path in ("/", "/index.html"):
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
        elif path == "/config":
            payload = dict(CONFIG.get(), appVersion=APP_VERSION)
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        elif path == "/matchlog/resume":
            self._send(200, json.dumps(MATCHLOG.last_clock_state(), ensure_ascii=False).encode("utf-8"))
        elif path.startswith("/logos/"):
            name = os.path.basename(path[len("/logos/"):])   # no traversal
            full = os.path.join(LOGO_DIR, name)
            ext  = os.path.splitext(name)[1].lower()
            ctype = {"": "application/octet-stream", ".png": "image/png",
                     ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "application/octet-stream")
            self._send_file(full, ctype)
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        path = unquote(self.path.split("?")[0])
        if path == "/config":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                patch = json.loads(self.rfile.read(n).decode("utf-8"))
                if not isinstance(patch, dict):
                    raise ValueError("body must be a JSON object")
                CONFIG.update(patch, from_http=True)
                self._send(200, json.dumps(CONFIG.get(), ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
        elif path == "/matchlog":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(n).decode("utf-8"))
                if payload.get("action") == "start":
                    MATCHLOG.start(payload)
                elif payload.get("action") == "score":
                    MATCHLOG.update_score(payload.get("homeScore", 0), payload.get("awayScore", 0))
                elif payload.get("action") == "clockEvent":
                    MATCHLOG.clock_event(payload.get("event", ""), payload.get("clockSeconds", 0),
                                          payload.get("period", 1), payload.get("wallClockAt", ""))
                else:
                    raise ValueError("unknown action")
                self._send(200, b'{"ok":true}')
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._send(404, b'{"error":"not found"}')


def start_http_server():
    srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


# ═════════════════════════════════════════════════════════════════════════════
# NETWORK: hostname + per-adapter IPs (LAN vs WiFi)
# ═════════════════════════════════════════════════════════════════════════════
def get_adapter_ips():
    """Return {'server': 'http://host.local:8080', 'lan': url|None, 'wifi': url|None}."""
    host = socket.gethostname()
    result = {"server": f"http://{host}.local:{HTTP_PORT}", "lan": None, "wifi": None}
    ips = []
    if os.name == "nt":
        try:
            out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                                 encoding="cp874", errors="replace",
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            adapter = ""
            for line in out.splitlines():
                if line and not line.startswith(" "):
                    adapter = line.strip().rstrip(":")
                m = re.search(r"IPv4[^:]*:\s*([\d.]+)", line)
                if m:
                    ips.append((adapter, m.group(1)))
        except Exception:
            pass
    if not ips:  # fallback: single best-guess IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(("LAN", s.getsockname()[0]))
            s.close()
        except Exception:
            pass
    for name, ip in ips:
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        url = f"http://{ip}:{HTTP_PORT}"
        lname = name.lower()
        if ("wi-fi" in lname or "wireless" in lname or "wlan" in lname) and not result["wifi"]:
            result["wifi"] = url
        elif not result["lan"]:
            result["lan"] = url
        elif not result["wifi"]:
            result["wifi"] = url
    return result


# ═════════════════════════════════════════════════════════════════════════════
# GUI WIDGET HELPERS (flat dark widgets on plain tk — no ttk theming pain)
# ═════════════════════════════════════════════════════════════════════════════
def rounded_rect(canvas, x1, y1, x2, y2, r=14, **kwargs):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def card(parent, title, icon="", accent=C["blue"]):
    """Card with rounded corners matching the web app's design. Plain Tk
    widgets are always square, so the background is hand-drawn on a Canvas
    and the real content sits in a Frame layered on top of it."""
    outer = tk.Frame(parent, bg=C["bg"])
    canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    inner = tk.Frame(canvas, bg=C["card"])
    win = canvas.create_window(0, 0, window=inner, anchor="nw")

    hdr = tk.Frame(inner, bg=C["card"])
    hdr.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(hdr, text=(icon + "  " if icon else "") + title, bg=C["card"],
             fg=accent, font=FONT_H, anchor="w").pack(side="left")
    body = tk.Frame(inner, bg=C["card"])
    body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    shape = {"id": None}

    def redraw(event=None):
        canvas.update_idletasks()
        w, h = canvas.winfo_width(), inner.winfo_reqheight()
        if w < 2 or h < 2:
            return
        canvas.itemconfigure(win, width=w)
        canvas.configure(height=h)
        if shape["id"]:
            canvas.delete(shape["id"])
        shape["id"] = rounded_rect(canvas, 1, 1, w - 1, h - 1, r=14,
                                    fill=C["card"], outline=C["border"])
        canvas.tag_lower(shape["id"])

    inner.bind("<Configure>", redraw)
    canvas.bind("<Configure>", redraw)
    return outer, body


def label(parent, text, **kw):
    return tk.Label(parent, text=text, bg=kw.pop("bg", C["card"]),
                    fg=kw.pop("fg", C["text2"]), font=kw.pop("font", FONT_SM),
                    anchor="w", **kw)


def entry(parent, textvar, width=18, mono=False):
    e = tk.Entry(parent, textvariable=textvar, width=width,
                 bg=C["input"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=FONT_MONO if mono else FONT,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["blue"])
    return e


def flat_button(parent, text, command, fg=C["text"], bg=C["card2"], font=FONT_SM, padx=10, pady=4):
    b = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
    b.configure(highlightthickness=1, highlightbackground=C["border"])
    b.bind("<Button-1>", lambda e: command())
    return b


class Dropdown(tk.Frame):
    """Flat-styled dropdown matching the app's dark theme (native tk.OptionMenu
    draws an OS-themed 3D indicator that clashes with the flat dark cards)."""
    def __init__(self, parent, options, variable, width=10, bg=C["card"]):
        super().__init__(parent, bg=bg)
        self.var = variable
        self.menu = tk.Menu(self, tearoff=0, bg=C["card2"], fg=C["text"],
                            activebackground=C["blue"], activeforeground=C["text"],
                            font=FONT_SM, bd=0)
        for opt in options:
            self.menu.add_command(label=opt if opt else "—", command=lambda o=opt: self.var.set(o))
        self.btn = tk.Label(self, bg=C["input"], fg=C["text"], font=FONT_SM,
                            padx=10, pady=5, width=width, anchor="w", cursor="hand2",
                            highlightthickness=1, highlightbackground=C["border"])
        self.btn.pack(fill="x")
        self.btn.bind("<Button-1>", self._popup)
        self.var.trace_add("write", lambda *a: self._refresh())
        self._refresh()

    def _refresh(self):
        self.btn.configure(text=f"{self.var.get() or '—'}   ▾")

    def _popup(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)


class Segmented(tk.Frame):
    """Two-or-more option segmented control, like the web app's mode buttons."""
    def __init__(self, parent, options, variable, accent=C["blue"], bg=C["card"]):
        super().__init__(parent, bg=bg)
        self.var = variable
        self.accent = accent
        self.btns = {}
        for value, text in options:
            b = tk.Label(self, text=text, font=FONT_SM, padx=12, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, v=value: self.set(v))
            self.btns[value] = b
        self.var.trace_add("write", lambda *a: self._paint())
        self._paint()

    def set(self, value):
        self.var.set(value)

    def _paint(self):
        cur = self.var.get()
        for v, b in self.btns.items():
            if v == cur:
                b.configure(bg=C["card2"], fg=self.accent,
                            highlightthickness=1, highlightbackground=self.accent)
            else:
                b.configure(bg=C["card"], fg=C["muted"],
                            highlightthickness=1, highlightbackground=C["border"])


class LogoDrop(tk.Frame):
    """Drag & Drop logo target. Copies the dropped file to C:\\vMixData\\logos
    and stores the filename in `variable`. Click = browse fallback."""
    def __init__(self, parent, title, variable, on_change):
        super().__init__(parent, bg=C["input"], highlightthickness=1,
                         highlightbackground=C["border"], cursor="hand2")
        self.var = variable
        self.on_change = on_change
        self.lbl = tk.Label(self, text="", bg=C["input"], fg=C["muted"],
                            font=FONT_SM, justify="center", pady=14)
        self.lbl.pack(fill="both", expand=True)
        self.title = title
        self._paint()
        self.lbl.bind("<Button-1>", lambda e: self.browse())
        self.bind("<Button-1>", lambda e: self.browse())
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DropEnter>>", lambda e: self.configure(highlightbackground=C["blue"]))
            self.dnd_bind("<<DropLeave>>", lambda e: self.configure(highlightbackground=C["border"]))
        self.var.trace_add("write", lambda *a: self._paint())

    def _paint(self):
        name = self.var.get()
        if name:
            self.lbl.configure(text=f"🖼  {name}\n(คลิกเพื่อเปลี่ยน / ลากไฟล์มาวางทับได้)", fg=C["cyan"])
        else:
            hint = "ลากไฟล์ PNG มาวางที่นี่" if HAS_DND else "คลิกเพื่อเลือกไฟล์ PNG"
            self.lbl.configure(text=f"⬇  {self.title}\n{hint}", fg=C["muted"])

    def _on_drop(self, event):
        self.configure(highlightbackground=C["border"])
        paths = self.tk.splitlist(event.data)
        if paths:
            self._take_file(paths[0])

    def browse(self):
        p = filedialog.askopenfilename(title=f"เลือกโลโก้ — {self.title}",
                                       filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
        if p:
            self._take_file(p)

    def _take_file(self, src):
        src = src.strip("{}")   # tkdnd wraps paths containing spaces in braces
        if not os.path.isfile(src):
            return
        os.makedirs(LOGO_DIR, exist_ok=True)
        name = os.path.basename(src)
        dst = os.path.join(LOGO_DIR, name)
        try:
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
            self.var.set(name)
            self.on_change()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"คัดลอกไฟล์ไม่สำเร็จ:\n{e}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═════════════════════════════════════════════════════════════════════════════
class App:
    def __init__(self):
        Root = TkinterDnD.Tk if HAS_DND else tk.Tk
        self.root = Root()
        self.root.title(f"{APP_NAME} — YRU Scoreboard Server v{APP_VERSION}")
        self.root.configure(bg=C["bg"])
        self.root.geometry("560x860")
        self.root.minsize(520, 700)
        self.tray_icon = None
        self._save_job = None

        self._build_vars()
        self._build_ui()
        self._load_from_config()
        self._poll_http_edits()   # GUI-thread polling for edits arriving via HTTP POST
        check_for_update(lambda ver, url: self.root.after(0, self._on_update_found, ver, url))

        # intercept close/minimize → tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Unmap>", self._on_unmap)

    # ── variables ────────────────────────────────────────────────────────────
    def _build_vars(self):
        v = {}
        v["matchMode"]  = tk.StringVar(value="thai")
        v["titleType"]  = tk.StringVar(value="logo")
        v["dayOfWeek"]  = tk.StringVar()
        v["date"]       = tk.StringVar()
        v["month"]      = tk.StringVar()
        v["year"]       = tk.StringVar()
        v["kickOff"]    = tk.StringVar(value="15:00")
        v["periodCount"] = tk.IntVar(value=2)
        v["periodMins"]  = tk.IntVar(value=45)
        v["clockMode"]  = tk.StringVar(value="continuous")
        v["compName"]   = tk.StringVar()
        v["compLogo"]   = tk.StringVar()
        v["homeName"]   = tk.StringVar(value="HOME")
        v["homeColor"]  = tk.StringVar(value="#1a3a6b")
        v["homeLogo"]   = tk.StringVar()
        v["awayName"]   = tk.StringVar(value="AWAY")
        v["awayColor"]  = tk.StringVar(value="#8b0000")
        v["awayLogo"]   = tk.StringVar()
        v["countdownDuration"] = tk.StringVar(value="7000")
        v["goalDuration"]      = tk.StringVar(value="13000")
        self.v = v
        # autosave on any change (debounced)
        for var in v.values():
            var.trace_add("write", lambda *a: self._schedule_save())

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Scrollable column
        canvas = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0)
        vsb = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.col = tk.Frame(canvas, bg=C["bg"])
        self.col.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=self.col, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        pad = {"fill": "x", "padx": 12, "pady": 6}

        # ── 1) CONNECTION (top-most, as requested) ────────────────────────────
        c1, b1 = card(self.col, "Connection — เปิดบนมือถือ/ไอแพด", "📡", C["green"])
        c1.pack(**pad)
        self.url_rows = {}
        for key, name in (("server", "Server"), ("lan", "Lan IP"), ("wifi", "WiFi IP")):
            row = tk.Frame(b1, bg=C["card"]); row.pack(fill="x", pady=3)
            label(row, f"{name} :", font=FONT_BOLD, fg=C["text"]).pack(side="left")
            url_lbl = tk.Label(row, text="—", bg=C["card"], fg=C["cyan"], font=FONT_MONO, anchor="w")
            url_lbl.pack(side="left", padx=(6, 6), fill="x", expand=True)
            btn = flat_button(row, "Copy", lambda k=key: self.copy_url(k), fg=C["blue"])
            btn.pack(side="right")
            self.url_rows[key] = url_lbl
        rowb = tk.Frame(b1, bg=C["card"]); rowb.pack(fill="x", pady=(6, 0))
        flat_button(rowb, "↻ Refresh IPs", self.refresh_urls, fg=C["text2"]).pack(side="left")
        flat_button(rowb, "🌐 เปิดเว็บแอพ", lambda: webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}"),
                    fg=C["green"]).pack(side="left", padx=6)
        label(b1, f"Data folder: {BASE_DIR}", fg=C["muted"]).pack(anchor="w", pady=(6, 0))
        prow = tk.Frame(b1, bg=C["card"]); prow.pack(fill="x", pady=(8, 0))
        flat_button(prow, "📂 โหลดรายการแข่งขัน", self.load_competition, fg=C["cyan"]).pack(side="left")
        flat_button(prow, "💾 บันทึกเป็นรายการใหม่", self.save_competition_as, fg=C["text2"]).pack(side="left", padx=6)
        prow2 = tk.Frame(b1, bg=C["card"]); prow2.pack(fill="x", pady=(6, 0))
        flat_button(prow2, "↩ กู้คืนค่าตั้งก่อนหน้า", self.restore_last_backup, fg=C["amber"]).pack(side="left")
        self.profile_status_var = tk.StringVar(value="ยังไม่ได้โหลดรายการแข่งขัน")
        tk.Label(b1, textvariable=self.profile_status_var, bg=C["card"], fg=C["muted"],
                 font=FONT_SM, anchor="w", justify="left", wraplength=520).pack(anchor="w", pady=(4, 0))
        self.update_url = None
        self.update_banner = tk.Label(b1, text="", bg=C["card"], fg=C["amber"], font=FONT_BOLD,
                                      cursor="hand2", anchor="w")
        self.update_banner.bind("<Button-1>", lambda e: self.update_url and webbrowser.open(self.update_url))

        # ── 2) SETUP MODE ─────────────────────────────────────────────────────
        c2, b2 = card(self.col, "Setup Mode", "⚙", C["blue"])
        c2.pack(**pad)
        r = tk.Frame(b2, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Match Mode", width=12).pack(side="left")
        Segmented(r, [("thai", "Thai League"), ("general", "General")], self.v["matchMode"]).pack(side="left")
        r = tk.Frame(b2, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Title Type", width=12).pack(side="left")
        Segmented(r, [("logo", "Logo"), ("title", "Title")], self.v["titleType"], accent=C["purple"]).pack(side="left")

        # ── 3) MATCH SETUP (date / kick off / periods) ────────────────────────
        c3, b3 = card(self.col, "Match Setup", "📅", C["cyan"])
        c3.pack(**pad)
        r = tk.Frame(b3, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Match Date", width=12).pack(side="left")
        if HAS_CAL:
            self.date_picker = DateEntry(r, width=14, font=FONT, locale="en_US",
                                         date_pattern="dd/mm/yyyy", firstweekday="sunday",
                                         showweeknumbers=False,
                                         # minimal chrome like the Windows 11 calendar flyout --
                                         # flat header (no solid accent bar), accent color reserved
                                         # for the selected-day highlight only
                                         background=C["card2"], foreground=C["text"],
                                         bordercolor=C["border"],
                                         headersbackground=C["card2"], headersforeground=C["muted"],
                                         normalbackground=C["card2"], normalforeground=C["text"],
                                         weekendbackground=C["card2"], weekendforeground=C["text2"],
                                         othermonthbackground=C["card2"], othermonthforeground=C["muted"],
                                         othermonthwebackground=C["card2"], othermonthweforeground=C["muted"],
                                         selectbackground=C["blue"], selectforeground="white")
            self.date_picker.pack(side="left")
            self.date_picker.bind("<<DateEntrySelected>>", lambda e: self._on_date_picked())
            label(r, "  (เลือกจากปฏิทิน กันลงวันผิด)", fg=C["muted"]).pack(side="left")
        else:
            label(r, "Day of Week", width=12).pack(side="left")
            Dropdown(r, DAYS, self.v["dayOfWeek"], width=10).pack(side="left")
            r = tk.Frame(b3, bg=C["card"]); r.pack(fill="x", pady=3)
            label(r, "Date", width=12).pack(side="left")
            entry(r, self.v["date"], width=5).pack(side="left")
            label(r, "  Month ").pack(side="left")
            Dropdown(r, MONTHS, self.v["month"], width=10).pack(side="left")
            label(r, "  Year ").pack(side="left")
            entry(r, self.v["year"], width=6).pack(side="left")
        r = tk.Frame(b3, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Kick Off", width=12).pack(side="left")
        entry(r, self.v["kickOff"], width=8, mono=True).pack(side="left")
        label(r, " (เช่น 15:00)").pack(side="left")
        r = tk.Frame(b3, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Periods", width=12).pack(side="left")
        Segmented(r, [(2, "2"), (3, "3"), (4, "4")], self.v["periodCount"], accent=C["cyan"]).pack(side="left")
        label(r, "   นาที/รอบ ").pack(side="left")
        entry(r, self.v["periodMins"], width=4).pack(side="left")
        r = tk.Frame(b3, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Clock Mode", width=12).pack(side="left")
        Segmented(r, [("continuous", "Cumulative (นับต่อเนื่อง)"), ("reset", "Reset Each (เริ่มนับ 0 ใหม่)")],
                  self.v["clockMode"], accent=C["cyan"]).pack(side="left")

        # ── 4) COMPETITION & TEAMS ────────────────────────────────────────────
        c4, b4 = card(self.col, "Competition & Teams", "🏆", C["purple"])
        c4.pack(**pad)
        r = tk.Frame(b4, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Competition", width=12).pack(side="left")
        entry(r, self.v["compName"], width=34).pack(side="left", fill="x", expand=True)
        LogoDrop(b4, "Competition Logo", self.v["compLogo"], self._schedule_save)\
            .pack(fill="x", pady=(4, 8))

        for team, accent in (("home", C["blue"]), ("away", C["red"])):
            tk.Frame(b4, bg=C["border"], height=1).pack(fill="x", pady=6)
            hd = tk.Frame(b4, bg=C["card"]); hd.pack(fill="x")
            sw = tk.Label(hd, text="  ", bg=self.v[f"{team}Color"].get()); sw.pack(side="left")
            label(hd, f"  {team.upper()} TEAM", font=FONT_BOLD, fg=C["text"]).pack(side="left")
            setattr(self, f"{team}_swatch", sw)
            r = tk.Frame(b4, bg=C["card"]); r.pack(fill="x", pady=3)
            label(r, "Team Name", width=12).pack(side="left")
            entry(r, self.v[f"{team}Name"], width=24).pack(side="left", fill="x", expand=True)
            r = tk.Frame(b4, bg=C["card"]); r.pack(fill="x", pady=3)
            label(r, "Team Color", width=12).pack(side="left")
            entry(r, self.v[f"{team}Color"], width=9, mono=True).pack(side="left")
            flat_button(r, "🎨 เลือกสี", lambda t=team: self.pick_color(t), fg=accent)\
                .pack(side="left", padx=6)
            self.v[f"{team}Color"].trace_add("write", lambda *a, t=team: self._paint_swatch(t))
            LogoDrop(b4, f"{team.capitalize()} Logo", self.v[f"{team}Logo"], self._schedule_save)\
                .pack(fill="x", pady=(4, 4))

        # ── 5) TIMING SETTINGS ────────────────────────────────────────────────
        c5, b5 = card(self.col, "Timing Settings", "⏱", C["amber"])
        c5.pack(**pad)
        r = tk.Frame(b5, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Countdown duration", width=18).pack(side="left")
        entry(r, self.v["countdownDuration"], width=8, mono=True).pack(side="left")
        label(r, " ms").pack(side="left")
        r = tk.Frame(b5, bg=C["card"]); r.pack(fill="x", pady=3)
        label(r, "Goal! duration", width=18).pack(side="left")
        entry(r, self.v["goalDuration"], width=8, mono=True).pack(side="left")
        label(r, " ms").pack(side="left")

        # footer
        f = tk.Frame(self.col, bg=C["bg"]); f.pack(fill="x", padx=12, pady=(4, 14))
        self.status_lbl = tk.Label(f, text="● Server running", bg=C["bg"], fg=C["green"], font=FONT_SM)
        self.status_lbl.pack(side="left")
        flat_button(f, "ซ่อนลง Tray", self.hide_to_tray, fg=C["text2"]).pack(side="right")

        self.refresh_urls()

    def _paint_swatch(self, team):
        try:
            getattr(self, f"{team}_swatch").configure(bg=self.v[f"{team}Color"].get())
        except tk.TclError:
            pass  # incomplete hex while typing

    # ── config sync ──────────────────────────────────────────────────────────
    def _schedule_save(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(400, self._save_now)

    def _save_now(self):
        self._save_job = None
        patch = {}
        for k, var in self.v.items():
            val = var.get()
            if k in ("periodCount",):
                try: val = int(val)
                except Exception: val = 2
            if k in ("periodMins", "countdownDuration", "goalDuration"):
                try: val = int(val)
                except Exception: val = DEFAULT_CONFIG[k]
            patch[k] = val
        CONFIG.update(patch)

    def _on_update_found(self, latest_version, url):
        self.update_url = url
        self.update_banner.configure(text=f"🔔 มีเวอร์ชันใหม่ v{latest_version} พร้อมใช้งาน — คลิกเพื่อดาวน์โหลด")
        self.update_banner.pack(anchor="w", pady=(6, 0))

    def _poll_http_edits(self):
        """Runs on the GUI thread — reload fields when a phone/iPad POSTed /config."""
        if CONFIG.dirty_from_http.is_set():
            CONFIG.dirty_from_http.clear()
            self._load_from_config()
            self.status_lbl.configure(text="✓ อัปเดตจากมือถือ/ไอแพด", fg=C["cyan"])
            self.root.after(2500, lambda: self.status_lbl.configure(text="● Server running", fg=C["green"]))
        self.root.after(500, self._poll_http_edits)

    def _load_from_config(self):
        data = CONFIG.get()
        # avoid save feedback loop while loading
        if self._save_job:
            self.root.after_cancel(self._save_job); self._save_job = None
        for k, var in self.v.items():
            val = data.get(k, DEFAULT_CONFIG.get(k, ""))
            if str(var.get()) != str(val):
                var.set(val)
        if self._save_job:  # cancel saves triggered by the sets above
            self.root.after_cancel(self._save_job); self._save_job = None
        self._sync_date_picker_from_vars()

    def _on_date_picked(self):
        d = self.date_picker.get_date()
        self.v["dayOfWeek"].set(DAYS[d.weekday() + 1])   # DAYS[1:]=Mon..Sun, matches weekday() 0..6
        self.v["date"].set(str(d.day))
        self.v["month"].set(MONTHS[d.month])             # MONTHS[1:]=Jan..Dec, matches d.month 1..12
        self.v["year"].set(str(d.year))

    def _sync_date_picker_from_vars(self):
        if not HAS_CAL or not hasattr(self, "date_picker"):
            return
        try:
            month_idx = MONTHS.index(self.v["month"].get())
            day = int(self.v["date"].get())
            year = int(self.v["year"].get())
            if month_idx and day and year:
                self.date_picker.set_date(datetime.date(year, month_idx, day))
        except (ValueError, IndexError):
            pass

    # ── competition profiles (load/save a whole match setup + logos folder) ───
    def load_competition(self):
        folder = filedialog.askdirectory(title="เลือกโฟลเดอร์รายการแข่งขัน (ต้องมี config.json)")
        if not folder:
            return
        cfg_path = os.path.join(folder, "config.json")
        if not os.path.exists(cfg_path):
            messagebox.showerror(APP_NAME, "ไม่พบ config.json ในโฟลเดอร์นี้")
            return
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"อ่านไฟล์ config ไม่ได้:\n{e}")
            return
        self._backup_current_config()   # snapshot the outgoing setup in case this load was a mistake
        src_logos = os.path.join(folder, "logos")
        if os.path.isdir(src_logos):
            os.makedirs(LOGO_DIR, exist_ok=True)
            for fn in os.listdir(src_logos):
                try:
                    shutil.copy2(os.path.join(src_logos, fn), os.path.join(LOGO_DIR, fn))
                except Exception:
                    pass
        CONFIG.update(data)
        self._load_from_config()
        self._paint_swatch("home"); self._paint_swatch("away")
        name = data.get("compName") or os.path.basename(folder)
        self.profile_status_var.set(
            f"รายการปัจจุบัน: {name} · โหลดเมื่อ {datetime.datetime.now():%d/%m/%Y %H:%M} · {folder}")

    def _backup_current_config(self):
        """Snapshot the current config.json before an action that overwrites it
        (loading a different competition), so a wrong pick can be undone."""
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"config-{ts}.json")
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(CONFIG.get(), f, ensure_ascii=False, indent=2)
            backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "config-*.json")))
            for old in backups[:-20]:   # keep only the most recent 20 backups
                try: os.remove(old)
                except Exception: pass
        except Exception:
            pass

    def restore_last_backup(self):
        backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "config-*.json")))
        if not backups:
            messagebox.showinfo(APP_NAME, "ยังไม่มีไฟล์สำรองครับ (จะสร้างให้อัตโนมัติทุกครั้งที่โหลดรายการแข่งขันใหม่)")
            return
        latest = backups[-1]
        if not messagebox.askyesno(APP_NAME,
                f"กู้คืนค่าตั้งจากไฟล์สำรอง\n{os.path.basename(latest)}\nกลับมาใช้แทนค่าปัจจุบันหรือไม่?"):
            return
        try:
            with open(latest, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"อ่านไฟล์สำรองไม่ได้:\n{e}")
            return
        CONFIG.update(data)
        self._load_from_config()
        self._paint_swatch("home"); self._paint_swatch("away")
        self.profile_status_var.set(
            f"กู้คืนค่าตั้งจากไฟล์สำรอง {os.path.basename(latest)} · {datetime.datetime.now():%d/%m/%Y %H:%M}")

    def save_competition_as(self):
        folder = filedialog.askdirectory(title="เลือกตำแหน่งที่จะบันทึกรายการแข่งขัน (จะสร้างโฟลเดอร์ย่อยให้)")
        if not folder:
            return
        name = (self.v["compName"].get() or "Competition").strip()
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", name) or "Competition"
        dest = os.path.join(folder, safe_name)
        try:
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "config.json"), "w", encoding="utf-8") as f:
                json.dump(CONFIG.get(), f, ensure_ascii=False, indent=2)
            dest_logos = os.path.join(dest, "logos")
            os.makedirs(dest_logos, exist_ok=True)
            if os.path.isdir(LOGO_DIR):
                for fn in os.listdir(LOGO_DIR):
                    shutil.copy2(os.path.join(LOGO_DIR, fn), os.path.join(dest_logos, fn))
        except Exception as e:
            messagebox.showerror(APP_NAME, f"บันทึกไม่สำเร็จ:\n{e}")
            return
        self.profile_status_var.set(
            f"รายการปัจจุบัน: {name} · บันทึกเมื่อ {datetime.datetime.now():%d/%m/%Y %H:%M} · {dest}")

    # ── connection URLs ──────────────────────────────────────────────────────
    def refresh_urls(self):
        urls = get_adapter_ips()
        self._urls = urls
        for k, lbl in self.url_rows.items():
            lbl.configure(text=urls.get(k) or "—")

    def copy_url(self, key):
        url = getattr(self, "_urls", {}).get(key)
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status_lbl.configure(text=f"✓ Copied {url}", fg=C["cyan"])
            self.root.after(2500, lambda: self.status_lbl.configure(text="● Server running", fg=C["green"]))

    # ── colors ───────────────────────────────────────────────────────────────
    def pick_color(self, team):
        cur = self.v[f"{team}Color"].get()
        rgb, hexv = colorchooser.askcolor(color=cur if cur.startswith("#") else None,
                                          title=f"เลือกสีทีม {team.upper()}")
        if hexv:
            self.v[f"{team}Color"].set(hexv)

    # ── tray ─────────────────────────────────────────────────────────────────
    def _on_unmap(self, event):
        # minimize button → tray (only when the toplevel itself is iconified)
        if event.widget is self.root and self.root.state() == "iconic":
            self.hide_to_tray()

    def hide_to_tray(self):
        if not HAS_TRAY:
            # no tray lib — just minimize normally
            self.root.iconify()
            return
        self.root.withdraw()
        if self.tray_icon is None:
            img = Image.new("RGB", (64, 64), C["bg"])
            d = ImageDraw.Draw(img)
            d.ellipse((8, 8, 56, 56), fill=C["blue"])
            d.text((22, 18), "V", fill="white")
            menu = pystray.Menu(
                pystray.MenuItem("เปิดหน้าต่าง", self._tray_show, default=True),
                pystray.MenuItem("เปิดเว็บแอพ", lambda: webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}")),
                pystray.MenuItem("Copy LAN URL", lambda: self.root.after(0, lambda: self.copy_url("lan"))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("ออกจากโปรแกรม", self._tray_exit),
            )
            self.tray_icon = pystray.Icon(APP_NAME, img, f"{APP_NAME} — running on :{HTTP_PORT}", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show(self):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()

    def _tray_exit(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        self.root.mainloop()


# ═════════════════════════════════════════════════════════════════════════════
def ensure_dirs():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(LOGO_DIR, exist_ok=True)
    # first run: copy bundled index.html next to the exe/script into C:\vMixData
    if not os.path.exists(INDEX_PATH):
        here = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        bundled = os.path.join(here, "index.html")
        if os.path.exists(bundled):
            shutil.copy2(bundled, INDEX_PATH)


def main():
    register_fonts()
    ensure_startup_shortcut()
    ensure_dirs()
    try:
        start_http_server()
    except OSError as e:
        messagebox.showerror(APP_NAME, f"เปิด HTTP server ที่ port {HTTP_PORT} ไม่ได้:\n{e}\n\n"
                                       f"อาจมีโปรแกรมอื่น (เช่น python -m http.server) ใช้ port นี้อยู่")
        return
    App().run()


if __name__ == "__main__":
    main()
