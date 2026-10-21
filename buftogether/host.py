"""
Windows Host for cross-platform KVM (Windows Host -> macOS Client).
- Intercepts mouse and keyboard inputs via low-level Win32 hooks (WH_MOUSE_LL, WH_KEYBOARD_LL).
- Routes mouse seamlessly across display borders (left or right edge).
- Forwards keyboard strokes with native macOS virtual keycodes mapping.
- Instant bidirectional clipboard synchronization via Win32 sequence numbers.
- Failsafes: ScrollLock hotkey to toggle, Pause key for emergency release, and connection watchdog.
"""

import sys
import time
import socket
import ctypes
import argparse
import threading
from ctypes import wintypes
from collections import deque

import pyperclip

try:
    from .protocol import send_msg, recv_msg
    from .keycodes import win_vk_to_mac, VK_SCROLL, VK_PAUSE
except ImportError:
    from protocol import send_msg, recv_msg
    from keycodes import win_vk_to_mac, VK_SCROLL, VK_PAUSE


# ============================================================
# Win32 Definitions & Structures
# ============================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_MOUSEHWHEEL = 0x020E

LLMHF_INJECTED = 0x00000001
LLKHF_EXTENDED = 0x00000001
LLKHF_INJECTED = 0x00000010
LLKHF_ALTDOWN = 0x00000020
LLKHF_UP = 0x00000080

PM_REMOVE = 0x0001

LRESULT = ctypes.c_ssize_t
HHOOK = ctypes.c_void_p
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
MonitorEnumProc = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(wintypes.RECT), ctypes.c_void_p,
)


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


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
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


# Win32 Function Signatures
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, MonitorEnumProc, ctypes.c_void_p]

user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]

user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]

user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [HHOOK]

user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]

user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]

user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]

user32.SetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

user32.ShowCursor.restype = ctypes.c_int
user32.ShowCursor.argtypes = [wintypes.BOOL]

user32.ClipCursor.restype = wintypes.BOOL
user32.ClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]

user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.GetClipboardSequenceNumber.argtypes = []

kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
kernel32.SetConsoleCtrlHandler.argtypes = [PHANDLER_ROUTINE, wintypes.BOOL]


# ============================================================
# Keyboard Layout Utilities
# ============================================================

def get_windows_keyboard_lang() -> str:
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return 'en'
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        klid = user32.GetKeyboardLayout(tid)
        return 'ru' if (klid & 0xFFFF) == 0x0419 else 'en'
    except Exception:
        return 'en'


def set_windows_keyboard_lang(lang: str):
    try:
        hwnd = user32.GetForegroundWindow()
        klid_str = '00000419' if lang == 'ru' else '00000409'
        hkl = user32.LoadKeyboardLayoutW(klid_str, 1)
        if hkl:
            user32.ActivateKeyboardLayout(hkl, 0)
            if hwnd:
                user32.PostMessageW(hwnd, 0x0050, 0, hkl)  # WM_INPUTLANGCHANGEREQUEST
    except Exception as e:
        print(f"[!] Failed to set Windows layout: {e}")


# ============================================================
# Host Application
# ============================================================

class WindowsHostApp:
    def __init__(self, port: int = 6000, edge: str = 'left', speed: float = 1.0, ctrl_as_cmd: bool = True):
        self.port = port
        self.edge = edge.lower()  # 'left' or 'right'
        self.speed = max(0.1, min(10.0, speed))
        self.ctrl_as_cmd = ctrl_as_cmd

        self.mode = 'LOCAL'  # 'LOCAL' or 'REMOTE'
        self.lock = threading.Lock()
        self.stop = threading.Event()

        # Keyboard layout sync
        self.current_lang = get_windows_keyboard_lang()

        # Display boundaries
        self.monitors = []
        self.border_monitor = None  # (l, t, r, b)
        self.client_w = 0
        self.client_h = 0

        # Virtual cursor state
        self.vx = 0.0
        self.vy = 0.0
        self.anchor = (0, 0)

        # Network connection
        self.conn: socket.socket | None = None
        self.conn_ok = False
        self.tx_queue = deque()
        self.tx_cv = threading.Condition()
        self.last_rx = time.time()
        self.watchdog_timeout = 4.0

        # Hooks
        self.mouse_hook = None
        self.kbd_hook = None
        self.mouse_proc = None
        self.kbd_proc = None
        self.ctrl_handler = None

        # Clipboard
        self.last_clipboard = ""
        self.last_seq = user32.GetClipboardSequenceNumber()

        # Modifier & language switch tracking
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.win_pressed = False
        self.non_mod_pressed = False
        self.combo_alt_shift = False
        self.combo_ctrl_shift = False

    # ---------- Monitors Setup ----------

    def detect_monitors(self):
        self.monitors = []

        def callback(h_monitor, hdc, lprc, data):
            r = lprc.contents
            self.monitors.append((r.left, r.top, r.right, r.bottom))
            return 1

        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), None)
        if not self.monitors:
            raise RuntimeError("No display monitors detected.")

        if self.edge == 'right':
            self.border_monitor = max(self.monitors, key=lambda m: m[2])
        else:
            self.border_monitor = min(self.monitors, key=lambda m: m[0])

        print(f"[*] Detected {len(self.monitors)} monitors: {self.monitors}")
        print(f"[*] Transition boundary monitor ({self.edge} edge): {self.border_monitor}")

    # ---------- State Transitions ----------

    def enter_remote(self, from_y: int) -> bool:
        if self.client_w == 0 or self.client_h == 0:
            return False

        with self.lock:
            self.mode = 'REMOTE'
            self.last_rx = time.time()

            l, t, r, b = self.border_monitor
            h = b - t
            rel = (from_y - t) / h if h > 0 else 0.5
            rel = max(0.0, min(1.0, rel))

            if self.edge == 'left':
                # Enter macOS on its right edge
                self.vx = float(self.client_w - 1)
                self.vy = rel * float(self.client_h - 1)
            else:
                # Enter macOS on its left edge
                self.vx = 0.0
                self.vy = rel * float(self.client_h - 1)

            # Center mouse in boundary monitor to collect smooth relative deltas
            cx, cy = (l + r) // 2, (t + b) // 2
            self.anchor = (cx, cy)
            user32.SetCursorPos(cx, cy)

            # Confine physical cursor inside boundary monitor
            clip = wintypes.RECT(l + 10, t + 10, r - 10, b - 10)
            user32.ClipCursor(ctypes.byref(clip))

            # Hide host cursor
            user32.ShowCursor(False)

            # Synchronize current Windows layout to macOS
            cur_lang = get_windows_keyboard_lang()
            self.current_lang = cur_lang
            self.queue_tx({'type': 'sync_layout', 'lang': cur_lang})

            self.queue_tx({
                'type': 'enter',
                'x': int(self.vx),
                'y': int(self.vy),
            })
            print(f"[→] CONTROL → macOS @ ({int(self.vx)}, {int(self.vy)}) [Layout: {cur_lang.upper()}]")
            return True

    def enter_local(self, silent: bool = False):
        with self.lock:
            if self.mode == 'LOCAL':
                return
            self.mode = 'LOCAL'

            # Release hardware cursor confinement
            user32.ClipCursor(None)

            l, t, r, b = self.border_monitor
            h = b - t
            rel = self.vy / max(1.0, float(self.client_h - 1))
            host_y = int(t + rel * (h - 1))
            host_y = max(t, min(b - 1, host_y))

            if self.edge == 'left':
                host_x = l + 2
            else:
                host_x = r - 2

            user32.SetCursorPos(host_x, host_y)
            user32.ShowCursor(True)

            # Restore synchronized layout on Windows
            set_windows_keyboard_lang(self.current_lang)

            if not silent:
                self.queue_tx({'type': 'leave'})
                self.queue_tx({'type': 'release_all'})
            print(f"[←] CONTROL → Windows @ ({host_x}, {host_y}) [Layout: {self.current_lang.upper()}]")

    # ---------- Hook Callbacks ----------

    def _mouse_hook_cb(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode < 0:
            return user32.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)

        info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if info.flags & LLMHF_INJECTED:
            return user32.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)

        px, py = info.pt.x, info.pt.y
        mode = self.mode

        if mode == 'LOCAL':
            l, t, r, b = self.border_monitor
            if self.edge == 'left' and px <= l:
                if self.enter_remote(py):
                    return 1
            elif self.edge == 'right' and px >= r - 1:
                if self.enter_remote(py):
                    return 1
            return user32.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)

        # Mode is REMOTE: handle all mouse actions
        if wParam == WM_MOUSEMOVE:
            ax, ay = self.anchor
            dx = (px - ax) * self.speed
            dy = (py - ay) * self.speed

            if dx == 0 and dy == 0:
                return 1

            self.vx += dx
            self.vy += dy

            # Check boundary crossings back to Windows
            if self.edge == 'left' and self.vx >= self.client_w:
                self.enter_local()
                return 1
            elif self.edge == 'right' and self.vx < 0:
                self.enter_local()
                return 1

            # Clamp coordinates to client screen
            self.vx = max(0.0, min(float(self.client_w - 1), self.vx))
            self.vy = max(0.0, min(float(self.client_h - 1), self.vy))

            # Recenter cursor to anchor
            user32.SetCursorPos(ax, ay)

            self.queue_tx({
                'type': 'move',
                'x': int(self.vx),
                'y': int(self.vy),
            })
            return 1

        # Mouse clicks
        btn_map = {
            WM_LBUTTONDOWN: ('left', 'down'),
            WM_LBUTTONUP: ('left', 'up'),
            WM_RBUTTONDOWN: ('right', 'down'),
            WM_RBUTTONUP: ('right', 'up'),
            WM_MBUTTONDOWN: ('middle', 'down'),
            WM_MBUTTONUP: ('middle', 'up'),
        }
        if wParam in btn_map:
            btn, act = btn_map[wParam]
            self.queue_tx({'type': 'button', 'button': btn, 'action': act})
            return 1

        # X-Buttons (Back / Forward)
        if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            xbtn = (info.mouseData >> 16) & 0xFFFF
            btn = 'x1' if xbtn == 1 else 'x2'
            act = 'down' if wParam == WM_XBUTTONDOWN else 'up'
            self.queue_tx({'type': 'button', 'button': btn, 'action': act})
            return 1

        # Scroll Wheel
        if wParam == WM_MOUSEWHEEL:
            delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
            self.queue_tx({'type': 'scroll', 'dy': delta // 120})
            return 1

        if wParam == WM_MOUSEHWHEEL:
            delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
            self.queue_tx({'type': 'scroll', 'dx': delta // 120})
            return 1

        return 1

    def _kbd_hook_cb(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode < 0:
            return user32.CallNextHookEx(self.kbd_hook, nCode, wParam, lParam)

        info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if info.flags & LLKHF_INJECTED:
            return user32.CallNextHookEx(self.kbd_hook, nCode, wParam, lParam)

        vk = info.vkCode
        is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        mode = self.mode

        # Toggle hotkey: ScrollLock
        if vk == VK_SCROLL and is_down:
            if mode == 'LOCAL':
                l, t, r, b = self.border_monitor
                self.enter_remote((t + b) // 2)
            else:
                self.enter_local()
            return 1

        # Emergency break hotkey: Pause
        if vk == VK_PAUSE:
            if mode == 'REMOTE':
                self.enter_local()
                return 1

        # In LOCAL mode: allow all other keys to pass
        if mode == 'LOCAL':
            return user32.CallNextHookEx(self.kbd_hook, nCode, wParam, lParam)

        # In REMOTE mode: consume key and translate to Mac Carbon keycode
        # Check language switch combinations (Alt+Shift, Ctrl+Shift, Mod+Space, CapsLock)
        if vk in (0x10, 0xA0, 0xA1):  # Shift
            if is_down:
                self.shift_pressed = True
                if self.alt_pressed and not self.non_mod_pressed:
                    self.combo_alt_shift = True
                if self.ctrl_pressed and not self.non_mod_pressed:
                    self.combo_ctrl_shift = True
            else:
                self.shift_pressed = False
                if self.combo_alt_shift:
                    self.combo_alt_shift = False
                    self.queue_tx({'type': 'switch_input_source'})
                    print("[*] Language switch triggered (Alt+Shift)")
                elif self.combo_ctrl_shift:
                    self.combo_ctrl_shift = False
                    self.queue_tx({'type': 'switch_input_source'})
                    print("[*] Language switch triggered (Ctrl+Shift)")

        elif vk in (0x12, 0xA4, 0xA5):  # Alt
            if is_down:
                self.alt_pressed = True
                if self.shift_pressed and not self.non_mod_pressed:
                    self.combo_alt_shift = True
            else:
                self.alt_pressed = False
                if self.combo_alt_shift:
                    self.combo_alt_shift = False
                    self.queue_tx({'type': 'switch_input_source'})
                    print("[*] Language switch triggered (Alt+Shift)")

        elif vk in (0x11, 0xA2, 0xA3):  # Ctrl
            if is_down:
                self.ctrl_pressed = True
                if self.shift_pressed and not self.non_mod_pressed:
                    self.combo_ctrl_shift = True
            else:
                self.ctrl_pressed = False
                if self.combo_ctrl_shift:
                    self.combo_ctrl_shift = False
                    self.queue_tx({'type': 'switch_input_source'})
                    print("[*] Language switch triggered (Ctrl+Shift)")

        elif vk in (0x5B, 0x5C):  # Win
            self.win_pressed = is_down

        elif vk == 0x20:  # Space
            if is_down and (self.win_pressed or self.ctrl_pressed or self.alt_pressed):
                self.queue_tx({'type': 'switch_input_source'})
                print("[*] Language switch triggered (Mod+Space)")
                return 1
            self.non_mod_pressed = True

        elif vk == 0x14:  # CapsLock
            if is_down:
                self.queue_tx({'type': 'switch_input_source'})
                print("[*] Language switch triggered (CapsLock)")
                return 1

        else:
            if is_down:
                self.non_mod_pressed = True
                self.combo_alt_shift = False
                self.combo_ctrl_shift = False
            else:
                if not (self.shift_pressed or self.alt_pressed or self.ctrl_pressed or self.win_pressed):
                    self.non_mod_pressed = False

        mac_code = win_vk_to_mac(vk, ctrl_as_cmd=self.ctrl_as_cmd)
        if mac_code is not None:
            self.queue_tx({
                'type': 'key',
                'mac': mac_code,
                'action': 'down' if is_down else 'up',
            })

        # Return 1 to suppress key event on Windows host while in REMOTE
        return 1

    # ---------- Networking & Queue ----------

    def queue_tx(self, msg: dict):
        if not self.conn_ok:
            return
        with self.tx_cv:
            self.tx_queue.append(msg)
            self.tx_cv.notify()

    def tx_loop(self):
        while self.conn_ok and not self.stop.is_set():
            with self.tx_cv:
                while not self.tx_queue and self.conn_ok:
                    self.tx_cv.wait(timeout=0.2)
                if not self.tx_queue:
                    continue
                msgs = list(self.tx_queue)
                self.tx_queue.clear()

            # Merge consecutive mouse move events to eliminate latency
            coalesced = []
            pending_move = None
            for m in msgs:
                if m.get('type') == 'move':
                    pending_move = m
                else:
                    if pending_move is not None:
                        coalesced.append(pending_move)
                        pending_move = None
                    coalesced.append(m)
            if pending_move is not None:
                coalesced.append(pending_move)

            for m in coalesced:
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

    def handle_client_msg(self, msg: dict):
        mtype = msg.get('type')
        if mtype == 'ping':
            try:
                send_msg(self.conn, {'type': 'pong'})
            except Exception:
                pass

        elif mtype == 'hello':
            with self.lock:
                self.client_w = int(msg.get('width', 0))
                self.client_h = int(msg.get('height', 0))
            print(f"[*] Client resolution: {self.client_w}x{self.client_h}")

        elif mtype == 'clipboard':
            text = msg.get('text', '')
            if text and text != self.last_clipboard:
                self.last_clipboard = text
                try:
                    pyperclip.copy(text)
                    self.last_seq = user32.GetClipboardSequenceNumber()
                    preview = text[:40].replace('\n', ' ')
                    print(f"[←] Clipboard from macOS ({len(text)} chars): {preview!r}")
                except Exception as e:
                    print(f"[!] Clipboard write error: {e}")

        elif mtype == 'layout_changed':
            lang = msg.get('lang', 'en')
            if lang != self.current_lang:
                self.current_lang = lang
                set_windows_keyboard_lang(lang)
                print(f"[★] Windows layout synchronized from macOS: {lang.upper()}")

    def watchdog_loop(self):
        while not self.stop.is_set():
            time.sleep(0.5)
            if self.mode == 'REMOTE':
                if not self.conn_ok or (time.time() - self.last_rx > self.watchdog_timeout):
                    print("[!] Watchdog: Client silent or disconnected. Returning control to Windows.")
                    self.enter_local(silent=True)

    def serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', self.port))
        srv.listen(1)
        print(f"[*] Host listening on port {self.port}...")

        while not self.stop.is_set():
            try:
                srv.settimeout(1.0)
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[+] Client connected from {addr}")
            self.conn = conn
            self.conn_ok = True
            self.last_rx = time.time()
            self.tx_queue.clear()

            t_tx = threading.Thread(target=self.tx_loop, daemon=True)
            t_rx = threading.Thread(target=self.rx_loop, daemon=True)
            t_tx.start()
            t_rx.start()

            while self.conn_ok and not self.stop.is_set():
                time.sleep(0.2)

            print("[*] Client disconnected. Waiting for connection...")
            try:
                conn.close()
            except Exception:
                pass
            self.conn = None
            if self.mode == 'REMOTE':
                self.enter_local(silent=True)

        srv.close()

    # ---------- Clipboard Sync ----------

    def clipboard_loop(self):
        while not self.stop.is_set():
            try:
                seq = user32.GetClipboardSequenceNumber()
                if seq != self.last_seq:
                    self.last_seq = seq
                    text = pyperclip.paste()
                    if text and text != self.last_clipboard:
                        self.last_clipboard = text
                        self.queue_tx({'type': 'clipboard', 'text': text})
                        preview = text[:40].replace('\n', ' ')
                        print(f"[→] Clipboard sent to macOS ({len(text)} chars): {preview!r}")
            except Exception:
                pass
            time.sleep(0.08)

    # ---------- Keyboard Layout Sync Loop ----------

    def layout_loop(self):
        while not self.stop.is_set():
            if self.conn_ok:
                try:
                    if self.mode == 'LOCAL':
                        cur = get_windows_keyboard_lang()
                        if cur != self.current_lang:
                            self.current_lang = cur
                            self.queue_tx({'type': 'sync_layout', 'lang': cur})
                            print(f"[*] Windows layout changed to {cur.upper()}, syncing to macOS")
                except Exception:
                    pass
            time.sleep(0.2)

    # ---------- Hooks & Lifecycle ----------

    def install_hooks(self):
        self.mouse_proc = HOOKPROC(self._mouse_hook_cb)
        self.kbd_proc = HOOKPROC(self._kbd_hook_cb)

        self.mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self.mouse_proc, None, 0)
        if not self.mouse_hook:
            raise OSError(f"SetWindowsHookExW(WH_MOUSE_LL) failed: {ctypes.get_last_error()}")

        self.kbd_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.kbd_proc, None, 0)
        if not self.kbd_hook:
            user32.UnhookWindowsHookEx(self.mouse_hook)
            raise OSError(f"SetWindowsHookExW(WH_KEYBOARD_LL) failed: {ctypes.get_last_error()}")

        print("[*] Low-level Mouse & Keyboard hooks installed.")
        print("[*] Failsafes: Press 'ScrollLock' to toggle or 'Pause' to force escape back to Windows.")

        def console_ctrl(ctrl_type):
            self.stop.set()
            return True

        self.ctrl_handler = PHANDLER_ROUTINE(console_ctrl)
        kernel32.SetConsoleCtrlHandler(self.ctrl_handler, True)

        msg = MSG()
        try:
            while not self.stop.is_set():
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.005)
        except KeyboardInterrupt:
            print("\n[*] Ctrl+C received, shutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        self.stop.set()
        user32.ClipCursor(None)
        user32.ShowCursor(True)

        if self.mouse_hook:
            try:
                user32.UnhookWindowsHookEx(self.mouse_hook)
            except Exception:
                pass
            self.mouse_hook = None

        if self.kbd_hook:
            try:
                user32.UnhookWindowsHookEx(self.kbd_hook)
            except Exception:
                pass
            self.kbd_hook = None

        if self.ctrl_handler:
            try:
                kernel32.SetConsoleCtrlHandler(self.ctrl_handler, False)
            except Exception:
                pass
            self.ctrl_handler = None

        print("[*] Hooks uninstalled, hardware cursor restored.")

    def run(self):
        self.detect_monitors()

        t_serve = threading.Thread(target=self.serve, daemon=True)
        t_clip = threading.Thread(target=self.clipboard_loop, daemon=True)
        t_watchdog = threading.Thread(target=self.watchdog_loop, daemon=True)
        t_layout = threading.Thread(target=self.layout_loop, daemon=True)

        t_serve.start()
        t_clip.start()
        t_watchdog.start()
        t_layout.start()

        try:
            self.install_hooks()
        finally:
            self.cleanup()
            time.sleep(0.2)
            print("[*] Host terminated.")


def main():
    parser = argparse.ArgumentParser(description="KVM Windows Host")
    parser.add_argument("--port", type=int, default=6000, help="Port to listen on (default: 6000)")
    parser.add_argument("--edge", choices=['left', 'right'], default='left', help="Border to cross into macOS (default: left)")
    parser.add_argument("--speed", type=float, default=1.0, help="Mouse speed multiplier (default: 1.0)")
    parser.add_argument("--no-swap-ctrl-cmd", action="store_true", help="Do not swap Ctrl and Cmd (keep Win=Cmd, Ctrl=Ctrl)")
    args = parser.parse_args()

    app = WindowsHostApp(
        port=args.port,
        edge=args.edge,
        speed=args.speed,
        ctrl_as_cmd=not args.no_swap_ctrl_cmd,
    )
    app.run()


if __name__ == '__main__':
    main()
