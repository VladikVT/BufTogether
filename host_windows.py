"""
Windows-хост.
- Синхронизирует буфер обмена с macOS-клиентом.
- Управляет мышью: когда курсор пересекает левый край самого левого
  монитора, управление уходит на клиента. Возврат — когда виртуальный
  курсор доходит до правого края экрана macOS.
"""

import ctypes
from ctypes import wintypes
import threading
import time
import socket
import sys
from collections import deque

import pyperclip

from protocol import send_msg, recv_msg

# ============================================================
# Win32
# ============================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

MonitorEnumProc = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(wintypes.RECT), ctypes.c_void_p,
)

WH_MOUSE_LL     = 14
WM_MOUSEMOVE    = 0x0200
WM_LBUTTONDOWN  = 0x0201
WM_LBUTTONUP    = 0x0202
WM_RBUTTONDOWN  = 0x0204
WM_RBUTTONUP    = 0x0205
WM_MBUTTONDOWN  = 0x0207
WM_MBUTTONUP    = 0x0208
WM_MOUSEWHEEL   = 0x020A
WM_MOUSEHWHEEL  = 0x020E

LRESULT = ctypes.c_ssize_t
HHOOK   = ctypes.c_void_p
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, MonitorEnumProc, ctypes.c_void_p
]
user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD
]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.ShowCursor.argtypes = [wintypes.BOOL]
user32.ShowCursor.restype = ctypes.c_int
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


# ============================================================
# Clipboard
# ============================================================

def get_clipboard():
    try:
        return pyperclip.paste()
    except Exception:
        return ""


def set_clipboard(text):
    try:
        pyperclip.copy(text)
    except Exception:
        pass


# ============================================================
# Host
# ============================================================

class HostApp:
    def __init__(self, port=6000):
        self.port = port
        self.mode = 'LOCAL'          # LOCAL | REMOTE
        self.lock = threading.Lock()

        # Monitors
        self.leftmost = None         # (l, t, r, b)
        self.client_w = 0
        self.client_h = 0

        # Virtual cursor on client
        self.vx = 0.0
        self.vy = 0.0

        # Anchor in REMOTE mode
        self.anchor = (0, 0)

        # Networking
        self.conn = None
        self.conn_ok = False
        self.tx = deque()
        self.tx_cv = threading.Condition()

        # Watchdog
        self.last_rx = time.time()
        self.watchdog_timeout = 2.0

        # Hook
        self.hook_proc = None
        self.hook_handle = None

        # Lifecycle
        self.stop = threading.Event()

        # Clipboard
        self.last_clipboard = get_clipboard()

    # ---------- monitors ----------

    def find_monitors(self):
        monitors = []

        def cb(hMonitor, hdc, lprc, data):
            r = lprc.contents
            monitors.append((r.left, r.top, r.right, r.bottom))
            return 1

        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(cb), None)
        return monitors

    # ---------- networking ----------

    def serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', self.port))
        srv.listen(1)
        print(f"[*] Host listening on port {self.port}")
        while not self.stop.is_set():
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[+] Client connected: {addr}")
            self.conn = conn
            self.conn_ok = True
            self.last_rx = time.time()
            self.tx.clear()

            threading.Thread(target=self.tx_loop, daemon=True).start()
            threading.Thread(target=self.rx_loop, daemon=True).start()
            threading.Thread(target=self.watchdog_loop, daemon=True).start()

            while self.conn_ok and not self.stop.is_set():
                time.sleep(0.2)

            print("[*] Client disconnected, waiting for reconnect...")
            try:
                conn.close()
            except Exception:
                pass
            self.conn = None
            with self.lock:
                if self.mode == 'REMOTE':
                    self.enter_local(silent=True)
        srv.close()

    def tx_loop(self):
        while self.conn_ok and not self.stop.is_set():
            with self.tx_cv:
                while not self.tx and self.conn_ok:
                    self.tx_cv.wait(timeout=0.5)
                if not self.tx:
                    continue
                msgs = list(self.tx)
                self.tx.clear()
            for m in msgs:
                try:
                    send_msg(self.conn, m)
                except Exception as e:
                    print(f"[!] TX error: {e}")
                    self.conn_ok = False
                    return

    def rx_loop(self):
        while self.conn_ok and not self.stop.is_set():
            try:
                msg = recv_msg(self.conn)
            except Exception as e:
                print(f"[!] RX error: {e}")
                break
            if msg is None:
                break
            self.last_rx = time.time()
            self.handle_client_msg(msg)
        self.conn_ok = False

    def watchdog_loop(self):
        while self.conn_ok and not self.stop.is_set():
            time.sleep(0.5)
            with self.lock:
                silent = (self.mode == 'REMOTE' and
                          time.time() - self.last_rx > self.watchdog_timeout)
                if silent:
                    print("[!] Watchdog: client silent, returning control to host")
                    self.enter_local(silent=True)

    def handle_client_msg(self, msg):
        t = msg.get('type')
        if t == 'hello':
            with self.lock:
                self.client_w = int(msg.get('width', 0))
                self.client_h = int(msg.get('height', 0))
            print(f"[*] Client screen: {self.client_w}x{self.client_h}")
        elif t == 'clipboard':
            text = msg.get('text', '')
            if text and text != self.last_clipboard:
                self.last_clipboard = text
                set_clipboard(text)
                print(f"[←] Clipboard from client: {text[:40]!r}")

    def queue_tx(self, msg):
        if not self.conn_ok:
            return
        with self.tx_cv:
            self.tx.append(msg)
            self.tx_cv.notify()

    # ---------- transitions ----------

    def enter_remote(self, from_y):
        """From hook thread. Returns True if we actually switched."""
        if self.client_w == 0 or self.client_h == 0:
            return False

        self.mode = 'REMOTE'
        l, t, r, b = self.leftmost
        h = b - t
        rel = (from_y - t) / h if h > 0 else 0.5
        rel = max(0.0, min(1.0, rel))
        self.vx = float(self.client_w - 1)
        self.vy = rel * (self.client_h - 1)

        # Anchor inside leftmost monitor (middle)
        self.anchor = ((l + r) // 2, (t + b) // 2)
        user32.ShowCursor(False)
        user32.SetCursorPos(self.anchor[0], self.anchor[1])

        self.queue_tx({'type': 'enter',
                       'x': int(self.vx), 'y': int(self.vy)})
        print(f"[→] Control → client @ ({int(self.vx)},{int(self.vy)})")
        return True

    def enter_local(self, silent=False):
        self.mode = 'LOCAL'
        l, t, r, b = self.leftmost
        h = b - t
        rel = self.vy / max(1.0, self.client_h - 1)
        y = int(t + rel * (h - 1))
        y = max(t, min(b - 1, y))
        user32.SetCursorPos(l + 1, y)
        user32.ShowCursor(True)
        if not silent:
            self.queue_tx({'type': 'leave'})
        print(f"[←] Control → host @ ({l+1},{y})")

    # ---------- hook ----------

    def install_hook(self):
        self.hook_proc = HOOKPROC(self._hook_cb)  # keep ref
        self.hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self.hook_proc, None, 0)
        if not self.hook_handle:
            raise OSError(f"SetWindowsHookEx failed: {ctypes.get_last_error()}")
        print("[*] Mouse hook installed")

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnhookWindowsHookEx(self.hook_handle)

    def _hook_cb(self, nCode, wParam, lParam):
        if nCode < 0:
            return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

        info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        px, py = info.pt.x, info.pt.y

        with self.lock:
            mode = self.mode
            leftmost = self.leftmost

        if mode == 'LOCAL':
            if leftmost is not None:
                l, t, r, b = leftmost
                if px <= l:
                    if self.enter_remote(py):
                        return 1  # consume — не пускаем дальше
            return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

        # REMOTE
        if wParam == WM_MOUSEMOVE:
            ax, ay = self.anchor
            dx = px - ax
            dy = py - ay
            if dx or dy:
                self.vx += dx
                self.vy += dy
                if self.vx >= self.client_w:
                    self.enter_local()
                    return 1
                if self.vx < 0:
                    self.vx = 0.0
                if self.vy < 0:
                    self.vy = 0.0
                elif self.vy > self.client_h - 1:
                    self.vy = float(self.client_h - 1)
                # Курсор ставим обратно в якорь, чтобы не упереться в край
                user32.SetCursorPos(ax, ay)
                self.queue_tx({'type': 'move',
                               'x': int(self.vx), 'y': int(self.vy)})
            return 1

        if wParam in (WM_LBUTTONDOWN, WM_LBUTTONUP,
                      WM_RBUTTONDOWN, WM_RBUTTONUP,
                      WM_MBUTTONDOWN, WM_MBUTTONUP):
            btn = {
                WM_LBUTTONDOWN: ('left', 'down'), WM_LBUTTONUP: ('left', 'up'),
                WM_RBUTTONDOWN: ('right', 'down'), WM_RBUTTONUP: ('right', 'up'),
                WM_MBUTTONDOWN: ('middle', 'down'), WM_MBUTTONUP: ('middle', 'up'),
            }[wParam]
            self.queue_tx({'type': 'button',
                           'button': btn[0], 'action': btn[1]})
            return 1

        if wParam == WM_MOUSEWHEEL:
            delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
            self.queue_tx({'type': 'scroll', 'dy': delta // 120})
            return 1

        if wParam == WM_MOUSEHWHEEL:
            delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
            self.queue_tx({'type': 'scroll', 'dx': delta // 120})
            return 1

        return 1  # всё прочее тоже потребляем, пока управление на клиенте

    # ---------- clipboard ----------

    def clipboard_loop(self):
        while not self.stop.is_set():
            try:
                cur = get_clipboard()
                if cur and cur != self.last_clipboard:
                    self.last_clipboard = cur
                    self.queue_tx({'type': 'clipboard', 'text': cur})
                    print(f"[→] Clipboard to client: {cur[:40]!r}")
            except Exception:
                pass
            time.sleep(1.0)

    # ---------- main ----------

    def run(self):
        monitors = self.find_monitors()
        if not monitors:
            print("[!] No monitors detected")
            return
        self.leftmost = min(monitors, key=lambda m: m[0])
        print(f"[*] Monitors: {monitors}")
        print(f"[*] Leftmost: {self.leftmost}")

        threading.Thread(target=self.serve, daemon=True).start()
        threading.Thread(target=self.clipboard_loop, daemon=True).start()

        try:
            self.install_hook()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop.set()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
    HostApp(port=port).run()