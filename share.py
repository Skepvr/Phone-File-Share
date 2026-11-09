#!/usr/bin/env python3
"""
LocalDrop - share files between your phone and computer over Wi-Fi.

Run this on your computer, then open the printed address in your phone's
browser. Files can be sent in both directions. No packages required.

Usage:
    python3 share.py                 # start on port 8000
    python3 share.py --port 9000     # use another port
    python3 share.py --pin 1234      # require a PIN
    python3 share.py --dir ~/Shared  # choose where files are stored
"""

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHUNK = 1024 * 256
CONFIG = {"dir": "shared", "pin": None}

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LocalDrop</title>
<style>
  :root { --bg:#f5f6f8; --card:#fff; --text:#1d2330; --muted:#6b7385;
          --accent:#3b6cf6; --border:#e1e4ea; --danger:#d64545; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#12151c; --card:#1b2030; --text:#e8ebf2; --muted:#8b93a7;
            --accent:#6b8cff; --border:#2a3144; --danger:#ff6b6b; } }
  * { box-sizing: border-box; }
  body { margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--text); }
  main { max-width:720px; margin:0 auto; padding:20px 16px 60px; }
  h1 { font-size:1.5rem; margin:8px 0 4px; }
  .sub { color:var(--muted); margin:0 0 20px; font-size:.95rem; }
  .card { background:var(--card); border:1px solid var(--border);
          border-radius:14px; padding:16px; margin-bottom:18px; }
  #drop { border:2px dashed var(--border); border-radius:14px; padding:28px 16px;
          text-align:center; cursor:pointer; transition:.15s; }
  #drop.over { border-color:var(--accent); background:rgba(59,108,246,.08); }
  #drop strong { display:block; font-size:1.05rem; margin-bottom:4px; }
  #drop span { color:var(--muted); font-size:.9rem; }
  button, .btn { font:inherit; border:0; border-radius:9px; padding:8px 14px;
          background:var(--accent); color:#fff; cursor:pointer; text-decoration:none;
          display:inline-block; }
  button.ghost { background:transparent; color:var(--danger);
          border:1px solid var(--border); }
  .row { display:flex; align-items:center; gap:10px; padding:12px 0;
         border-top:1px solid var(--border); }
  .row:first-child { border-top:0; }
  .info { flex:1; min-width:0; }
  .name { font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .meta { color:var(--muted); font-size:.82rem; }
  .actions { display:flex; gap:6px; }
  .bar { height:6px; background:var(--border); border-radius:4px; margin-top:6px; overflow:hidden; }
  .bar > i { display:block; height:100%; width:0; background:var(--accent); transition:width .1s; }
  .head { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
  .head h2 { font-size:1.05rem; margin:0; }
  .empty { color:var(--muted); text-align:center; padding:18px 0; }
  .err { color:var(--danger); font-size:.85rem; }
  #login { display:none; }
  input[type=password] { font:inherit; padding:9px 12px; border-radius:9px;
          border:1px solid var(--border); background:var(--bg); color:var(--text); }
</style>
</head>
<body>
<main>
  <h1>LocalDrop</h1>
  <p class="sub">Send files between your devices. Anything uploaded here can be downloaded from any device on this network.</p>

  <div class="card" id="login">
    <p>This share is protected. Enter the PIN shown on the computer.</p>
    <input type="password" id="pin" placeholder="PIN" inputmode="numeric">
    <button onclick="savePin()">Unlock</button>
  </div>

  <div id="app">
    <div class="card">
      <div id="drop">
        <strong>Tap to choose files</strong>
        <span>or drag and drop them here</span>
      </div>
      <input type="file" id="picker" multiple hidden>
      <div id="uploads"></div>
    </div>

    <div class="card">
      <div class="head"><h2>Shared files</h2><button onclick="refresh()">Refresh</button></div>
      <div id="list"></div>
    </div>
  </div>
</main>

<script>
const $ = id => document.getElementById(id);
const drop = $('drop'), picker = $('picker');

function getPin() { try { return sessionStorage.getItem('pin') || ''; } catch(e) { return ''; } }
function savePin() {
  const v = $('pin').value;
  try { sessionStorage.setItem('pin', v); } catch(e) {}
  document.cookie = 'pin=' + encodeURIComponent(v) + '; path=/; SameSite=Strict';
  refresh();
}
function authHeaders() { return { 'X-Pin': getPin() }; }
if (getPin()) document.cookie = 'pin=' + encodeURIComponent(getPin()) + '; path=/; SameSite=Strict';

function fmtSize(n) {
  const u = ['B','KB','MB','GB','TB']; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(1) : n) + ' ' + u[i];
}
function fmtTime(t) { return new Date(t * 1000).toLocaleString(); }
function esc(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function refresh() {
  const r = await fetch('/api/files', { headers: authHeaders() });
  if (r.status === 401) { $('login').style.display = 'block'; $('app').style.display = 'none'; return; }
  $('login').style.display = 'none'; $('app').style.display = 'block';
  const files = await r.json();
  const list = $('list');
  if (!files.length) { list.innerHTML = '<div class="empty">No files yet.</div>'; return; }
  list.innerHTML = files.map(f => `
    <div class="row">
      <div class="info">
        <div class="name">${esc(f.name)}</div>
        <div class="meta">${fmtSize(f.size)} · ${fmtTime(f.modified)}</div>
      </div>
      <div class="actions">
        <a class="btn" href="/files/${encodeURIComponent(f.name)}" download>Download</a>
        <button class="ghost" data-name="${esc(f.name)}" onclick="del(this.dataset.name)">Delete</button>
      </div>
    </div>`).join('');
}

async function del(name) {
  if (!confirm('Delete ' + name + '?')) return;
  await fetch('/api/files/' + encodeURIComponent(name), { method: 'DELETE', headers: authHeaders() });
  refresh();
}

function upload(file) {
  return new Promise(resolve => {
    const el = document.createElement('div');
    el.className = 'row';
    el.innerHTML = `<div class="info"><div class="name">${esc(file.name)}</div>
      <div class="bar"><i></i></div><div class="meta">Starting…</div></div>`;
    $('uploads').prepend(el);
    const bar = el.querySelector('i'), meta = el.querySelector('.meta');
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));
    xhr.setRequestHeader('X-Pin', getPin());
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) {
        bar.style.width = (e.loaded / e.total * 100) + '%';
        meta.textContent = fmtSize(e.loaded) + ' of ' + fmtSize(e.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status === 200) { bar.style.width = '100%'; meta.textContent = 'Done'; }
      else { meta.innerHTML = '<span class="err">Failed (' + xhr.status + ')</span>'; }
      resolve();
    };
    xhr.onerror = () => { meta.innerHTML = '<span class="err">Network error</span>'; resolve(); };
    xhr.send(file);
  });
}

async function handleFiles(files) {
  for (const f of files) await upload(f);
  refresh();
}

drop.onclick = () => picker.click();
picker.onchange = () => { handleFiles([...picker.files]); picker.value = ''; };
['dragenter','dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => handleFiles([...e.dataTransfer.files]));

refresh();
setInterval(() => { if ($('app').style.display !== 'none') refresh(); }, 5000);
</script>
</body>
</html>
"""


def safe_name(raw):
    """Reduce a client-supplied filename to a safe base name."""
    name = os.path.basename(raw.replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    return name[:200] or "file"


def unique_path(folder, name):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(name)
    n = 1
    while True:
        path = os.path.join(folder, f"{stem} ({n}){ext}")
        if not os.path.exists(path):
            return path
        n += 1


def lan_ip():
    """Best-effort detection of this computer's LAN address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is actually sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalDrop/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s  %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---- helpers ----
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        pin = CONFIG["pin"]
        if not pin:
            return True
        supplied = self.headers.get("X-Pin", "")
        if not supplied:
            cookies = self.headers.get("Cookie", "")
            m = re.search(r"(?:^|;\s*)pin=([^;]*)", cookies)
            supplied = urllib.parse.unquote(m.group(1)) if m else ""
        return supplied == pin

    def deny(self):
        self.send_json({"error": "PIN required"}, 401)

    def file_path(self, encoded_name):
        name = safe_name(urllib.parse.unquote(encoded_name))
        path = os.path.join(CONFIG["dir"], name)
        return name, path

    # ---- routes ----
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/files":
            if not self.authorized():
                return self.deny()
            files = []
            for entry in os.scandir(CONFIG["dir"]):
                if entry.is_file() and not entry.name.startswith("."):
                    st = entry.stat()
                    files.append({"name": entry.name, "size": st.st_size,
                                  "modified": st.st_mtime})
            files.sort(key=lambda f: f["modified"], reverse=True)
            self.send_json(files)
        elif path.startswith("/files/"):
            if not self.authorized():
                return self.deny()
            name, full = self.file_path(path[len("/files/"):])
            if not os.path.isfile(full):
                return self.send_json({"error": "Not found"}, 404)
            size = os.path.getsize(full)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            quoted = urllib.parse.quote(name)
            self.send_header("Content-Disposition",
                             f"attachment; filename*=UTF-8''{quoted}")
            self.end_headers()
            with open(full, "rb") as f:
                while True:
                    chunk = f.read(CHUNK)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/api/upload":
            return self.send_json({"error": "Not found"}, 404)
        if not self.authorized():
            return self.deny()
        raw_name = urllib.parse.unquote(self.headers.get("X-Filename", ""))
        length = int(self.headers.get("Content-Length", 0))
        if not raw_name:
            return self.send_json({"error": "Missing X-Filename"}, 400)
        dest = unique_path(CONFIG["dir"], safe_name(raw_name))
        tmp = dest + ".part"
        remaining = length
        try:
            with open(tmp, "wb") as f:
                while remaining > 0:
                    chunk = self.rfile.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ConnectionError("client disconnected")
                    f.write(chunk)
                    remaining -= len(chunk)
            os.replace(tmp, dest)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            return self.send_json({"error": "Upload failed"}, 500)
        self.send_json({"saved": os.path.basename(dest)})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/files/"):
            return self.send_json({"error": "Not found"}, 404)
        if not self.authorized():
            return self.deny()
        _, full = self.file_path(path[len("/api/files/"):])
        if os.path.isfile(full):
            os.remove(full)
            self.send_json({"deleted": True})
        else:
            self.send_json({"error": "Not found"}, 404)


def main():
    ap = argparse.ArgumentParser(description="Share files between phone and computer.")
    ap.add_argument("--port", type=int, default=8000, help="port (default 8000)")
    ap.add_argument("--dir", default="shared", help="folder for shared files (default ./shared)")
    ap.add_argument("--pin", default=None, help="require this PIN to use the share")
    args = ap.parse_args()

    CONFIG["dir"] = os.path.abspath(os.path.expanduser(args.dir))
    CONFIG["pin"] = args.pin
    os.makedirs(CONFIG["dir"], exist_ok=True)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        sys.exit(f"Could not start on port {args.port}: {e}\nTry --port 9000")

    ip = lan_ip()
    print("\n  LocalDrop is running\n")
    print(f"  On this computer:   http://localhost:{args.port}")
    print(f"  On your phone:      http://{ip}:{args.port}")
    print(f"  Files saved in:     {CONFIG['dir']}")
    if args.pin:
        print(f"  PIN:                {args.pin}")
    print("\n  Phone and computer must be on the same Wi-Fi. Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
