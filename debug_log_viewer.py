#!/usr/bin/env python3
"""
Python DebugLog viewer replacement for DebugLog.swf.

Listens on a TCP port for log messages forwarded by the Flash bridge (DebugLogBridge.swf).

Usage:
  1. Start the viewer:  python debug_log_viewer.py [--port 8765]
  2. Run the Flash bridge SWF (DebugLogBridge.swf)
  3. Run the game

Options:
  --port PORT         Listen port (default 8765)
  --no-exclude-download  Do not exclude Downloadovor/Download manager logs by default
  --exclude SENDER    Additional sender substring to exclude (can repeat)
"""

from __future__ import annotations

import argparse
import json
import queue
import socket
import sys
import threading
import time
from collections import deque
from typing import Optional

# Optional tkinter for GUI
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False

DEFAULT_PORT = 8765
MAX_DISPLAY_CHARS = 500_000
DEFAULT_EXCLUDE_SENDERS = ("download", "downloadovor", "downloadmanager")
RECV_BUFFER_SIZE = 65536

FLASH_POLICY_REQUEST = b"<policy-file-request/>"
FLASH_POLICY_RESPONSE = (
    b'<?xml version="1.0"?>'
    b'<cross-domain-policy>'
    b'<allow-access-from domain="*" to-ports="*"/>'
    b"</cross-domain-policy>\x00"
)


def parse_args():
    p = argparse.ArgumentParser(description="Nanovor DebugLog Viewer")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP listen port")
    p.add_argument(
        "--no-exclude-download",
        action="store_true",
        help="Do not exclude Downloadovor/Download manager logs",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="SENDER",
        help="Exclude logs whose sender contains this (case-insensitive, can repeat)",
    )

    return p.parse_args()


def extract_sender(msg: str) -> str:
    """First token of message is typically the sender (e.g. 'Nanovor 1')."""
    if not msg:
        return ""
    
    parts = msg.split(None, 1)

    return (parts[0] or "").lower()


def should_exclude(msg: str, exclude_senders: tuple[str, ...]) -> bool:
    if not exclude_senders:
        return False
    
    sender = extract_sender(msg)
    msg_lower = msg.lower()

    for exc in exclude_senders:
        if exc in sender or exc in msg_lower:
            return True
    
    return False


def format_log_line(cmd: str, msg: str, ts: Optional[float] = None, tie_breaker: Optional[int] = None) -> str:
    if ts is not None:
        tstr = time.strftime("%H:%M:%S", time.localtime(ts / 1000.0)) if ts > 1e10 else str(ts)
    else:
        tstr = time.strftime("%H:%M:%S", time.localtime())

    prefix = f"{tstr}|"

    if cmd == "error":
        prefix += " ERROR "
    elif cmd == "comment":
        prefix += " COMMENT "

    return prefix + msg + "\n"


class LogServer:
    def __init__(self, port: int, exclude_senders: tuple[str, ...], log_queue: queue.Queue):
        self.port = port
        self.exclude_senders = exclude_senders
        self.log_queue = log_queue
        self._sock: Optional[socket.socket] = None
        self._clients: list[socket.socket] = []
        self._running = True
        self._lock = threading.Lock()

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.listen(4)
        self._sock.settimeout(1.0)

        th = threading.Thread(target=self._accept_loop, daemon=True)
        th.start()

        print(f"[DebugLog] Listening on 127.0.0.1:{self.port} (run the bridge SWF to connect)", file=sys.stderr)

    def stop(self):
        self._running = False

        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except Exception:
                    pass
            self._clients.clear()

        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self._running and self._sock:
            try:
                conn, _ = self._sock.accept()
                with self._lock:
                    self._clients.append(conn)
                threading.Thread(target=self._serve_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    raise
                break

    def _serve_client(self, conn: socket.socket):
        buffer = b""

        try:
            conn.settimeout(1.0)
            while self._running:
                try:
                    data = conn.recv(RECV_BUFFER_SIZE)
                except socket.timeout:
                    continue

                if not data:
                    break

                buffer += data

                if FLASH_POLICY_REQUEST in buffer:
                    end = buffer.find(b"\x00", buffer.find(FLASH_POLICY_REQUEST))

                    if end != -1:
                        conn.sendall(FLASH_POLICY_RESPONSE)
                        buffer = buffer[end + 1 :].lstrip()

                while b"\n" in buffer or b"\r" in buffer:
                    line, _, buffer = buffer.partition(b"\n")
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        obj = json.loads(line.decode("utf-8", errors="replace"))
                    except Exception:
                        continue

                    cmd = obj.get("cmd")

                    if cmd == "clear":
                        self.log_queue.put(("clear", None))
                        continue

                    if cmd in ("log", "error", "comment"):
                        msg = obj.get("msg", "")

                        if should_exclude(msg, self.exclude_senders):
                            continue

                        ts = obj.get("ts")
                        tie = obj.get("tieBreaker")
                        self.log_queue.put((cmd, (msg, ts, tie)))
        except Exception:
            pass
        finally:
            with self._lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            try:
                conn.close()
            except Exception:
                pass


def run_console(port: int, exclude_senders: tuple[str, ...]):
    """Simple console output."""
    log_queue: queue.Queue = queue.Queue()
    server = LogServer(port, exclude_senders, log_queue)
    server.start()

    try:
        while True:
            try:
                item = log_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item[0] == "clear":
                print("\n--- CLEAR ---\n")
                continue
            cmd, (msg, ts, tie) = item
            line = format_log_line(cmd, msg, ts, tie)
            print(line, end="")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


def run_gui(port: int, exclude_senders: tuple[str, ...]):
    """Tkinter GUI with filter and exclude options."""
    if not HAS_TK:
        print("tkinter not available, falling back to console mode", file=sys.stderr)
        run_console(port, exclude_senders)
        return

    log_queue: queue.Queue = queue.Queue()
    server = LogServer(port, exclude_senders, log_queue)
    server.start()

    root = tk.Tk()
    root.title("Nanovor DebugLog")
    root.geometry("900x600")
    root.minsize(400, 200)

    # Filter
    filter_frame = ttk.Frame(root, padding=4)
    filter_frame.pack(fill=tk.X)
    ttk.Label(filter_frame, text="Filter (text):").pack(side=tk.LEFT, padx=(0, 4))
    filter_var = tk.StringVar()
    filter_entry = ttk.Entry(filter_frame, textvariable=filter_var, width=30)
    filter_entry.pack(side=tk.LEFT, padx=(0, 8))
    ttk.Label(filter_frame, text="Exclude senders:").pack(side=tk.LEFT, padx=(8, 4))
    exclude_var = tk.StringVar(value=", ".join(exclude_senders))
    exclude_entry = ttk.Entry(filter_frame, textvariable=exclude_var, width=35)
    exclude_entry.pack(side=tk.LEFT, padx=(0, 8))
    clear_button = ttk.Button(filter_frame, text="Clear log")
    clear_button.pack(side=tk.LEFT, padx=(0, 4))
    refilter_button = ttk.Button(filter_frame, text="Refilter")
    refilter_button.pack(side=tk.LEFT)

    # Log area
    text_frame = ttk.Frame(root, padding=4)
    text_frame.pack(fill=tk.BOTH, expand=True)
    log_text = scrolledtext.ScrolledText(
        text_frame,
        wrap=tk.WORD,
        font=tkfont.Font(family="Consolas", size=10),
        state=tk.DISABLED,
        maxundo=-1,
    )
    log_text.pack(fill=tk.BOTH, expand=True)

    # Store lines for filtering (we keep last N to avoid huge memory)
    log_buffer: deque = deque(maxlen=100_000)
    display_chars = [0]  # mutable so closure can update

    def get_exclude_set():
        raw = exclude_var.get().strip()

        if not raw:
            return set()

        return {s.strip().lower() for s in raw.split(",") if s.strip()}

    def apply_filter_to_line(line: str) -> bool:
        f = filter_var.get().strip().lower()

        if f and f not in line.lower():
            return False

        exc = get_exclude_set()

        if exc:
            first = (line.split("|", 1)[-1].split(None, 1)[0] if "|" in line else line.split(None, 1)[0]).lower()

            for e in exc:
                if e in first or e in line.lower():
                    return False
        
        return True

    def append_line(line: str, from_queue: bool = True):
        if from_queue:
            log_buffer.append(line)

        if not apply_filter_to_line(line):
            return

        log_text.configure(state=tk.NORMAL)
        log_text.insert(tk.END, line)
        display_chars[0] += len(line)

        while display_chars[0] > MAX_DISPLAY_CHARS and log_text.index("end-1c") != "1.0":
            head = log_text.get("1.0", "2.0")
            log_text.delete("1.0", "2.0")
            display_chars[0] -= len(head)
        
        log_text.configure(state=tk.DISABLED)
        log_text.see(tk.END)

    def do_clear():
        log_text.configure(state=tk.NORMAL)
        log_text.delete("1.0", tk.END)
        log_text.configure(state=tk.DISABLED)
        display_chars[0] = 0
        log_buffer.clear()

    def on_clear_click():
        do_clear()

    def on_refilter_click():
        log_text.configure(state=tk.NORMAL)
        log_text.delete("1.0", tk.END)
        log_text.configure(state=tk.DISABLED)
        display_chars[0] = 0

        for line in log_buffer:
            append_line(line, from_queue=False)

    clear_button.configure(command=on_clear_click)
    refilter_button.configure(command=on_refilter_click)

    def process_queue():
        try:
            while True:
                item = log_queue.get_nowait()
                if item[0] == "clear":
                    do_clear()
                    continue
                cmd, (msg, ts, tie) = item
                line = format_log_line(cmd, msg, ts, tie)
                append_line(line)
        except queue.Empty:
            pass
        root.after(50, process_queue)

    root.after(50, process_queue)

    def on_closing():
        server.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def main():
    args = parse_args()
    exclude = list(args.exclude)

    if not args.no_exclude_download:
        exclude.extend(DEFAULT_EXCLUDE_SENDERS)
    
    exclude_senders = tuple(s.strip().lower() for s in exclude if s.strip())

    if HAS_TK:
        run_gui(args.port, exclude_senders)
    else:
        run_console(args.port, exclude_senders)


if __name__ == "__main__":
    main()
