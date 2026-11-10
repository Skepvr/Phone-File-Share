#!/usr/bin/env python3
"""
LocalDrop (desktop window)

A friendly window around the LocalDrop server in share.py:
start/stop sharing, scan a QR code with your phone, pick the shared folder,
set a PIN, and see/manage the shared files.

Needs only Python with tkinter (included with Python on Windows and macOS;
on Linux install it with:  sudo apt install python3-tk).

Run:   python3 gui.py
Keep this file in the same folder as share.py.
"""

import json
import os
import queue
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer

import share

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # handled in main()
    tk = None

APP_NAME = "LocalDrop"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".localdrop.json")
DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), "LocalDrop")
QR_PX = 250


def fmt_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    n = float(n)
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{int(n)} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def open_folder(path):
    """Show a folder in the system file manager."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # Windows only
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


class ShareServer:
    """Runs the share.py HTTP server on a background thread."""

    def __init__(self, log):
        self.log = log
        self.httpd = None
        self.thread = None
        self.url = ""

    @property
    def running(self):
        return self.httpd is not None

    def start(self, port, folder, pin):
        """Start sharing. Returns the address phones should open.
        Raises OSError if the port is unavailable."""
        os.makedirs(folder, exist_ok=True)
        log = self.log

        class GuiHandler(share.Handler):
            def log_message(self, fmt, *args):  # no console in a windowed app
                log(fmt % args)

        httpd = ThreadingHTTPServer(("0.0.0.0", port), GuiHandler)
        share.CONFIG["dir"] = folder
        share.CONFIG["pin"] = pin or None
        self.url = f"http://{share.lan_ip()}:{port}"
        share.CONFIG["url"] = self.url
        self.httpd = httpd
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.url

    def stop(self):
        if not self.httpd:
            return
        httpd, self.httpd = self.httpd, None
        httpd.shutdown()
        httpd.server_close()
        if self.thread:
            self.thread.join(timeout=3)
        self.thread = None
        self.url = ""

    def qr_target(self, pin):
        """What the QR code opens (includes the PIN so scanning logs in)."""
        if pin:
            return self.url + "/?pin=" + urllib.parse.quote(pin)
        return self.url


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.minsize(760, 520)

        saved = load_settings()
        self.folder = tk.StringVar(value=saved.get("folder") or DEFAULT_FOLDER)
        self.port = tk.StringVar(value=str(saved.get("port") or 8000))
        self.use_pin = tk.BooleanVar(value=saved.get("use_pin", True))
        self.pin = tk.StringVar(value="%04d" % secrets.randbelow(10000))
        self.status = tk.StringVar(value="Stopped")
        self.url_text = tk.StringVar(value="")

        self.logq = queue.Queue()
        self.server = ShareServer(lambda msg: self.logq.put(msg))
        self._file_sig = None

        self._build()
        self._update_controls()
        self._draw_qr(None)
        self._poll_log()
        self._refresh_files()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.Frame(root, padding=14)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Frame(root, padding=(0, 14, 14, 14))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        # ---- left: status, QR, settings
        ttk.Label(left, text=APP_NAME, font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        self.status_lbl = ttk.Label(left, textvariable=self.status)
        self.status_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.qr = tk.Canvas(left, width=QR_PX, height=QR_PX, highlightthickness=1,
                            highlightbackground="#c8ccd4")
        self.qr.grid(row=2, column=0, columnspan=3)
        ttk.Label(left, text="Scan with your phone's camera",
                  foreground="#6b7385").grid(row=3, column=0, columnspan=3, pady=(4, 0))

        url_row = ttk.Frame(left)
        url_row.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 10))
        url_row.columnconfigure(0, weight=1)
        ttk.Entry(url_row, textvariable=self.url_text, state="readonly",
                  justify="center").grid(row=0, column=0, sticky="ew")
        self.copy_btn = ttk.Button(url_row, text="Copy", width=6, command=self.copy_url)
        self.copy_btn.grid(row=0, column=1, padx=(6, 0))

        self.start_btn = ttk.Button(left, text="Start sharing", command=self.toggle)
        self.start_btn.grid(row=5, column=0, columnspan=3, sticky="ew", ipady=6)

        ttk.Separator(left).grid(row=6, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(left, text="Folder").grid(row=7, column=0, sticky="w")
        self.folder_entry = ttk.Entry(left, textvariable=self.folder, width=26)
        self.folder_entry.grid(row=7, column=1, sticky="ew", padx=6)
        self.browse_btn = ttk.Button(left, text="Browse…", width=8, command=self.browse)
        self.browse_btn.grid(row=7, column=2)

        ttk.Label(left, text="Port").grid(row=8, column=0, sticky="w", pady=(8, 0))
        self.port_spin = ttk.Spinbox(left, from_=1024, to=65535, textvariable=self.port,
                                     width=8)
        self.port_spin.grid(row=8, column=1, sticky="w", padx=6, pady=(8, 0))

        self.pin_check = ttk.Checkbutton(left, text="Require PIN", variable=self.use_pin,
                                         command=self._update_controls)
        self.pin_check.grid(row=9, column=0, sticky="w", pady=(8, 0))
        self.pin_entry = ttk.Entry(left, textvariable=self.pin, width=10)
        self.pin_entry.grid(row=9, column=1, sticky="w", padx=6, pady=(8, 0))

        # ---- right: files and activity
        head = ttk.Frame(right)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Shared files", font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, sticky="w")
        ttk.Button(head, text="Add files…", command=self.add_files).grid(row=0, column=1)
        ttk.Button(head, text="Open folder", command=self.open_shared).grid(
            row=0, column=2, padx=(6, 0))
        ttk.Button(head, text="Delete selected", command=self.delete_selected).grid(
            row=0, column=3, padx=(6, 0))

        ttk.Label(right, text="Files you add here can be downloaded on your phone. "
                              "Files sent from your phone appear here.",
                  foreground="#6b7385", wraplength=420).grid(
            row=1, column=0, sticky="w", pady=(2, 6))

        tree_frame = ttk.Frame(right)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("size", "modified"),
                                 selectmode="extended")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("modified", text="Modified", anchor="w")
        self.tree.column("#0", width=240, stretch=True)
        self.tree.column("size", width=80, anchor="e", stretch=False)
        self.tree.column("modified", width=140, stretch=False)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        ttk.Label(right, text="Activity", font=("TkDefaultFont", 10, "bold")).grid(
            row=3, column=0, sticky="w", pady=(10, 2))
        log_frame = ttk.Frame(right)
        log_frame.grid(row=4, column=0, sticky="ew")
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=6, state="disabled", wrap="none",
                           relief="flat", borderwidth=1, highlightthickness=1,
                           highlightbackground="#c8ccd4")
        self.log.grid(row=0, column=0, sticky="ew")

    def _update_controls(self):
        running = self.server.running
        idle = "disabled" if running else "normal"
        for w in (self.folder_entry, self.browse_btn, self.port_spin, self.pin_check):
            w.config(state=idle)
        self.pin_entry.config(
            state="disabled" if running or not self.use_pin.get() else "normal")
        self.start_btn.config(text="Stop sharing" if running else "Start sharing")
        self.copy_btn.config(state="normal" if running else "disabled")
        self.status.set("● Sharing: ready for your phone" if running else "○ Stopped")

    def _draw_qr(self, target):
        c = self.qr
        c.delete("all")
        if not target:
            c.config(bg="#eef0f4")
            c.create_text(QR_PX // 2, QR_PX // 2, text="Press “Start sharing”\nto show the QR code",
                          justify="center", fill="#6b7385")
            return
        try:
            m = share.make_qr(target)
        except ValueError:
            c.config(bg="#eef0f4")
            c.create_text(QR_PX // 2, QR_PX // 2, justify="center", fill="#6b7385",
                          text="Address too long for a QR code.\nUse a shorter PIN.")
            return
        border = 3
        n = len(m) + 2 * border
        cell = max(2, QR_PX // n)
        off = (QR_PX - cell * n) // 2
        c.config(bg="white")
        for y, row in enumerate(m):
            for x, dark in enumerate(row):
                if dark:
                    x0 = off + (x + border) * cell
                    y0 = off + (y + border) * cell
                    c.create_rectangle(x0, y0, x0 + cell, y0 + cell,
                                       fill="black", outline="black")

    # ------------------------------------------------------------- actions
    def toggle(self):
        if self.server.running:
            self.server.stop()
            self.url_text.set("")
            self._draw_qr(None)
            self._add_log("Stopped sharing")
        else:
            self.start()
        self._update_controls()

    def start(self):
        try:
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_NAME, "Port must be a number between 1 and 65535.")
            return
        pin = self.pin.get().strip() if self.use_pin.get() else None
        if self.use_pin.get() and not pin:
            messagebox.showerror(APP_NAME, "Enter a PIN, or untick “Require PIN”.")
            return
        folder = os.path.abspath(os.path.expanduser(self.folder.get().strip()
                                                    or DEFAULT_FOLDER))
        try:
            url = self.server.start(port, folder, pin)
        except OSError as e:
            messagebox.showerror(
                APP_NAME,
                f"Could not start on port {port}:\n{e}\n\nTry a different port.")
            return
        self.folder.set(folder)
        self.url_text.set(url)
        self._draw_qr(self.server.qr_target(pin))
        self._add_log(f"Sharing {folder}")
        self._add_log(f"Phone address: {url}" + ("  (PIN required)" if pin else ""))
        save_settings({"folder": folder, "port": port, "use_pin": bool(pin)})
        self._file_sig = None
        self._refresh_files()

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.folder.get() or DEFAULT_FOLDER,
                                    title="Choose the folder to share")
        if d:
            self.folder.set(d)
            self._file_sig = None
            self._refresh_files()

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url_text.get())
        self._add_log("Address copied")

    def shared_dir(self):
        return os.path.abspath(os.path.expanduser(self.folder.get().strip()
                                                  or DEFAULT_FOLDER))

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Choose files to share with your phone")
        if not paths:
            return
        folder = self.shared_dir()
        os.makedirs(folder, exist_ok=True)
        for p in paths:
            try:
                dest = share.unique_path(folder, share.safe_name(os.path.basename(p)))
                shutil.copy2(p, dest)
                self._add_log(f"Added {os.path.basename(dest)}")
            except OSError as e:
                messagebox.showerror(APP_NAME, f"Could not add {os.path.basename(p)}:\n{e}")
        self._file_sig = None
        self._refresh_files()

    def open_shared(self):
        folder = self.shared_dir()
        os.makedirs(folder, exist_ok=True)
        open_folder(folder)

    def delete_selected(self):
        names = list(self.tree.selection())
        if not names:
            return
        what = names[0] if len(names) == 1 else f"{len(names)} files"
        if not messagebox.askyesno(APP_NAME, f"Delete {what}? This cannot be undone."):
            return
        folder = self.shared_dir()
        for name in names:
            try:
                os.remove(os.path.join(folder, share.safe_name(name)))
                self._add_log(f"Deleted {name}")
            except OSError as e:
                messagebox.showerror(APP_NAME, f"Could not delete {name}:\n{e}")
        self._file_sig = None
        self._refresh_files()

    # ------------------------------------------------------------ updating
    def _add_log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {msg}\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _poll_log(self):
        try:
            while True:
                self._add_log(self.logq.get_nowait())
        except queue.Empty:
            pass
        self.root.after(250, self._poll_log)

    def _refresh_files(self):
        folder = self.shared_dir()
        entries = []
        try:
            for e in os.scandir(folder):
                if e.is_file() and not e.name.startswith(".") \
                        and not e.name.endswith(".part"):
                    st = e.stat()
                    entries.append((e.name, st.st_size, st.st_mtime))
        except OSError:
            pass
        entries.sort(key=lambda t: t[2], reverse=True)
        if entries != self._file_sig:  # only rebuild when something changed
            self._file_sig = entries
            keep = set(self.tree.selection())
            self.tree.delete(*self.tree.get_children())
            for name, size, mtime in entries:
                self.tree.insert("", "end", iid=name, text=name, values=(
                    fmt_size(size),
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))))
            present = [n for n in keep if self.tree.exists(n)]
            if present:
                self.tree.selection_set(present)
        self.root.after(2000, self._refresh_files)

    def on_close(self):
        self.server.stop()
        self.root.destroy()


def main():
    if tk is None:
        sys.exit(
            "tkinter is not installed, so the window can't open.\n"
            "  Windows/macOS: reinstall Python from python.org (tkinter is included).\n"
            "  Ubuntu/Debian: sudo apt install python3-tk\n"
            "  Fedora:        sudo dnf install python3-tkinter\n"
            "You can still run the command-line version:  python3 share.py")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
