"""
macOS Client for cross-platform KVM (Windows Host -> macOS Client).
- Receives mouse movement, button clicks, and scroll events.
- Injects native Quartz mouse events with dragging support.
- Injects native Quartz keyboard events with modifier tracking.
- Synchronizes clipboard bidirectionally with zero-latency NSPasteboard changeCount polling.
- Safely hides/shows cursor and recovers gracefully on disconnect or exit.
"""

import sys
import time
import socket
import argparse
import threading
from typing import Set

import Quartz
from AppKit import NSPasteboard, NSStringPboardType
import objc
from Foundation import NSBundle

try:
    from .protocol import send_msg, recv_msg
except ImportError:
    from protocol import send_msg, recv_msg


class InputSourceManager:
    def __init__(self):
        self.sources = []
        try:
            bundle = NSBundle.bundleWithPath_("/System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework")
            functions = [
                ("TISCopyCurrentKeyboardLayoutInputSource", b"@"),
                ("TISCreateInputSourceList", b"@@Z"),
                ("TISSelectInputSource", b"i@"),
                ("TISGetInputSourceProperty", b"@@@"),
            ]
            variables = [
                ("kTISPropertyInputSourceID", b"@"),
                ("kTISPropertyInputSourceCategory", b"@"),
                ("kTISCategoryKeyboardInputSource", b"@"),
            ]
            objc.loadBundleFunctions(bundle, globals(), functions)
            objc.loadBundleVariables(bundle, globals(), variables)
            self.update_sources()
        except Exception as e:
            print(f"[!] InputSourceManager init warning: {e}")

    def update_sources(self):
        try:
            all_src = TISCreateInputSourceList(None, False)
            self.sources = [
                s for s in all_src
                if str(TISGetInputSourceProperty(s, kTISPropertyInputSourceCategory)) == "TISCategoryKeyboardInputSource"
            ]
        except Exception as e:
            print(f"[!] InputSourceManager update error: {e}")

    def get_current_lang(self) -> str:
        try:
            cur = TISCopyCurrentKeyboardLayoutInputSource()
            sid = str(TISGetInputSourceProperty(cur, kTISPropertyInputSourceID)).lower()
            if "rus" in sid:
                return "ru"
            return "en"
        except Exception:
            return "en"

    def set_lang(self, lang: str) -> bool:
        try:
            if not self.sources:
                self.update_sources()
            for s in self.sources:
                sid = str(TISGetInputSourceProperty(s, kTISPropertyInputSourceID)).lower()
                if lang == "ru" and "rus" in sid:
                    TISSelectInputSource(s)
                    return True
                elif lang == "en" and any(x in sid for x in ("abc", "us", "en")):
                    TISSelectInputSource(s)
                    return True
            return False
        except Exception as e:
            print(f"[!] InputSourceManager set_lang error: {e}")
            return False

    def toggle(self) -> str:
        cur = self.get_current_lang()
        target = "ru" if cur == "en" else "en"
        self.set_lang(target)
        return target


# Modifier masks in Quartz
MOD_FLAG_MAP = {
    0x38: Quartz.kCGEventFlagMaskShift,       # Left Shift
    0x3C: Quartz.kCGEventFlagMaskShift,       # Right Shift
    0x37: Quartz.kCGEventFlagMaskCommand,     # Left Command
    0x36: Quartz.kCGEventFlagMaskCommand,     # Right Command
    0x3A: Quartz.kCGEventFlagMaskAlternate,   # Left Option
    0x3D: Quartz.kCGEventFlagMaskAlternate,   # Right Option
    0x3B: Quartz.kCGEventFlagMaskControl,     # Left Control
    0x3E: Quartz.kCGEventFlagMaskControl,     # Right Control
    0x39: Quartz.kCGEventFlagMaskAlphaShift,  # Caps Lock
}


class MacOSClient:
    def __init__(self, host: str, port: int = 6000):
        self.host = host
        self.port = port
        self.stop = threading.Event()
        self.sock: socket.socket | None = None
        self.connected = False

        # Display & Cursor
        self.main_display = Quartz.CGMainDisplayID()
        bounds = Quartz.CGDisplayBounds(self.main_display)
        self.screen_w = int(bounds.size.width)
        self.screen_h = int(bounds.size.height)
        self.cur_x = float(self.screen_w // 2)
        self.cur_y = float(self.screen_h // 2)
        self.cursor_hidden = False

        # Input state tracking
        self.pressed_keys: Set[int] = set()
        self.flags = 0
        self.buttons_down = {
            'left': False,
            'right': False,
            'middle': False,
            'x1': False,
            'x2': False,
        }

        # Clipboard
        self.pb = NSPasteboard.generalPasteboard()
        self.last_change_count = self.pb.changeCount()
        self.last_clipboard = self.get_pasteboard()

        # Input source manager
        self.input_mgr = InputSourceManager()
        self.current_lang = self.input_mgr.get_current_lang()

    # ==================== Cursor & Mouse ====================

    def warp(self, x: float, y: float):
        self.cur_x = max(0.0, min(float(self.screen_w - 1), float(x)))
        self.cur_y = max(0.0, min(float(self.screen_h - 1), float(y)))
        Quartz.CGWarpMouseCursorPosition((self.cur_x, self.cur_y))

    def hide_cursor(self):
        if not self.cursor_hidden:
            Quartz.CGDisplayHideCursor(self.main_display)
            self.cursor_hidden = True

    def show_cursor(self):
        if self.cursor_hidden:
            Quartz.CGDisplayShowCursor(self.main_display)
            self.cursor_hidden = False

    def post_mouse_move(self, x: float, y: float):
        self.warp(x, y)
        loc = (self.cur_x, self.cur_y)

        # Decide event type based on dragged state
        if self.buttons_down['left']:
            etype = Quartz.kCGEventLeftMouseDragged
            cg_btn = Quartz.kCGMouseButtonLeft
        elif self.buttons_down['right']:
            etype = Quartz.kCGEventRightMouseDragged
            cg_btn = Quartz.kCGMouseButtonRight
        elif self.buttons_down['middle']:
            etype = Quartz.kCGEventOtherMouseDragged
            cg_btn = Quartz.kCGMouseButtonCenter
        else:
            etype = Quartz.kCGEventMouseMoved
            cg_btn = Quartz.kCGMouseButtonLeft

        evt = Quartz.CGEventCreateMouseEvent(None, etype, loc, cg_btn)
        if evt:
            Quartz.CGEventSetFlags(evt, self.flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    def post_mouse_button(self, button: str, action: str):
        is_down = (action == 'down')
        self.buttons_down[button] = is_down

        btn_map = {
            'left': (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft),
            'right': (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight),
            'middle': (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGMouseButtonCenter),
            'x1': (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, 3),
            'x2': (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, 4),
        }
        ev_down, ev_up, cg_btn = btn_map.get(button, (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, 0))
        etype = ev_down if is_down else ev_up

        loc = (self.cur_x, self.cur_y)
        evt = Quartz.CGEventCreateMouseEvent(None, etype, loc, cg_btn)
        if evt:
            Quartz.CGEventSetFlags(evt, self.flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    def post_scroll(self, dx: int, dy: int):
        if dy:
            evt = Quartz.CGEventCreateScrollWheelEvent(
                None, Quartz.kCGScrollEventUnitLine, 1, int(dy)
            )
            if evt:
                Quartz.CGEventSetFlags(evt, self.flags)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        if dx:
            evt = Quartz.CGEventCreateScrollWheelEvent(
                None, Quartz.kCGScrollEventUnitLine, 2, 0, int(dx)
            )
            if evt:
                Quartz.CGEventSetFlags(evt, self.flags)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    # ==================== Keyboard ====================

    def post_key(self, mac_code: int, is_down: bool):
        # Update modifier mask if key is a modifier
        mod_mask = MOD_FLAG_MAP.get(mac_code)
        if mod_mask:
            if is_down:
                self.flags |= mod_mask
            else:
                self.flags &= ~mod_mask

        if is_down:
            self.pressed_keys.add(mac_code)
        else:
            self.pressed_keys.discard(mac_code)

        evt = Quartz.CGEventCreateKeyboardEvent(None, mac_code, is_down)
        if evt:
            Quartz.CGEventSetFlags(evt, self.flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    def release_all(self):
        """Releases all active keys and buttons to prevent stuck states."""
        for key in list(self.pressed_keys):
            evt = Quartz.CGEventCreateKeyboardEvent(None, key, False)
            if evt:
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        self.pressed_keys.clear()
        self.flags = 0

        for btn in list(self.buttons_down.keys()):
            if self.buttons_down[btn]:
                self.post_mouse_button(btn, 'up')

    # ==================== Clipboard ====================

    def get_pasteboard(self) -> str:
        try:
            val = self.pb.stringForType_(NSStringPboardType)
            return str(val) if val is not None else ""
        except Exception:
            return ""

    def set_pasteboard(self, text: str):
        try:
            self.pb.clearContents()
            self.pb.setString_forType_(text, NSStringPboardType)
            self.last_change_count = self.pb.changeCount()
        except Exception as e:
            print(f"[!] Pasteboard write error: {e}")

    def clipboard_loop(self):
        """Monitors macOS clipboard changes with high-frequency check."""
        while not self.stop.is_set():
            if self.connected and self.sock:
                try:
                    cnt = self.pb.changeCount()
                    if cnt != self.last_change_count:
                        self.last_change_count = cnt
                        text = self.get_pasteboard()
                        if text and text != self.last_clipboard:
                            self.last_clipboard = text
                            send_msg(self.sock, {'type': 'clipboard', 'text': text})
                            preview = text[:40].replace('\n', ' ')
                            print(f"[→] Clipboard sent to host ({len(text)} chars): {preview!r}")
                except Exception as e:
                    print(f"[!] Clipboard loop error: {e}")
            time.sleep(0.08)

    # ==================== Networking & Dispatch ====================

    def handle_msg(self, msg: dict):
        mtype = msg.get('type')
        if mtype == 'enter':
            self.show_cursor()
            x = msg.get('x', self.screen_w - 1)
            y = msg.get('y', self.screen_h // 2)
            self.post_mouse_move(x, y)
            print(f"[+] Control acquired @ ({int(x)}, {int(y)})")

        elif mtype == 'leave':
            self.release_all()
            self.hide_cursor()
            print("[-] Control relinquished to host")

        elif mtype == 'move':
            self.post_mouse_move(msg['x'], msg['y'])

        elif mtype == 'button':
            self.post_mouse_button(msg['button'], msg['action'])

        elif mtype == 'scroll':
            self.post_scroll(msg.get('dx', 0), msg.get('dy', 0))

        elif mtype == 'key':
            mac_code = msg.get('mac')
            if mac_code is not None:
                self.post_key(mac_code, msg.get('action') == 'down')

        elif mtype == 'release_all':
            self.release_all()

        elif mtype == 'sync_layout':
            lang = msg.get('lang', 'en')
            if lang != self.current_lang:
                self.current_lang = lang
                self.input_mgr.set_lang(lang)
                print(f"[★] Layout synchronized from host: {lang.upper()}")

        elif mtype == 'switch_input_source':
            self.release_all()
            new_lang = self.input_mgr.toggle()
            self.current_lang = new_lang
            print(f"[★] Input source switched: {new_lang.upper()}")
            if self.connected and self.sock:
                try:
                    send_msg(self.sock, {'type': 'layout_changed', 'lang': new_lang})
                except Exception:
                    pass

        elif mtype == 'clipboard':
            text = msg.get('text', '')
            if text and text != self.last_clipboard:
                self.last_clipboard = text
                self.set_pasteboard(text)
                preview = text[:40].replace('\n', ' ')
                print(f"[←] Clipboard from host ({len(text)} chars): {preview!r}")

        elif mtype == 'ping':
            try:
                send_msg(self.sock, {'type': 'pong'})
            except Exception:
                pass

    def connect_loop(self):
        while not self.stop.is_set():
            s = None
            try:
                print(f"[*] Connecting to {self.host}:{self.port}...")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.settimeout(5.0)
                s.connect((self.host, self.port))
                s.settimeout(None)

                self.sock = s
                self.connected = True
                print(f"[+] Connected to host! Screen: {self.screen_w}x{self.screen_h}")

                # Send initial handshake
                send_msg(self.sock, {
                    'type': 'hello',
                    'width': self.screen_w,
                    'height': self.screen_h,
                })

                # By default cursor is hidden while host has local control
                self.hide_cursor()

                # Process incoming stream
                while not self.stop.is_set() and self.connected:
                    msg = recv_msg(self.sock)
                    if msg is None:
                        break
                    self.handle_msg(msg)

            except Exception as e:
                print(f"[!] Connection error: {e}")
            finally:
                self.connected = False
                self.release_all()
                self.hide_cursor()
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass
                self.sock = None

            if not self.stop.is_set():
                print("[*] Reconnecting in 2 seconds...")
                time.sleep(2.0)

    def heartbeat_loop(self):
        while not self.stop.is_set():
            if self.connected and self.sock:
                try:
                    send_msg(self.sock, {'type': 'ping'})
                except Exception:
                    pass
            time.sleep(1.0)

    def layout_loop(self):
        while not self.stop.is_set():
            if self.connected and self.sock:
                try:
                    cur = self.input_mgr.get_current_lang()
                    if cur != self.current_lang:
                        self.current_lang = cur
                        send_msg(self.sock, {'type': 'layout_changed', 'lang': cur})
                        print(f"[★] Local macOS layout changed to {cur.upper()}, notifying host")
                except Exception:
                    pass
            time.sleep(0.2)

    def run(self):
        t_clip = threading.Thread(target=self.clipboard_loop, daemon=True)
        t_ping = threading.Thread(target=self.heartbeat_loop, daemon=True)
        t_layout = threading.Thread(target=self.layout_loop, daemon=True)
        t_clip.start()
        t_ping.start()
        t_layout.start()

        try:
            self.connect_loop()
        finally:
            self.stop.set()
            self.release_all()
            self.show_cursor()
            print("[*] Client terminated, cursor restored.")


def main():
    parser = argparse.ArgumentParser(description="KVM macOS Client")
    parser.add_argument("host", help="Host IP (e.g. 192.168.0.143)")
    parser.add_argument("--port", type=int, default=6000, help="Host port (default 6000)")
    args = parser.parse_args()

    client = MacOSClient(host=args.host, port=args.port)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        client.stop.set()
        client.release_all()
        client.show_cursor()


if __name__ == '__main__':
    main()
