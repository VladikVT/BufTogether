"""
macOS-клиент.
- Получает от хоста события мыши и применяет их локально.
- Прячет курсор, когда управление на хосте.
- Синхронизирует буфер обмена.
- Автоматически переподключается к хосту.
"""

import socket
import threading
import time
import sys

import Quartz
import pyperclip

from protocol import send_msg, recv_msg


class ClientApp:
    def __init__(self, host, port=6000):
        self.host = host
        self.port = port
        self.stop = threading.Event()
        self.sock = None
        self.connected = False
        self.cursor_hidden = False

        self.main_display = Quartz.CGMainDisplayID()
        bounds = Quartz.CGDisplayBounds(self.main_display)
        self.screen_w = int(bounds.size.width)
        self.screen_h = int(bounds.size.height)

        self.last_clipboard = pyperclip.paste()

    # ---------- cursor ----------

    def warp(self, x, y):
        x = max(0, min(self.screen_w - 1, int(x)))
        y = max(0, min(self.screen_h - 1, int(y)))
        Quartz.CGWarpMouseCursorPosition((float(x), float(y)))

    def hide_cursor(self):
        if not self.cursor_hidden:
            Quartz.CGDisplayHideCursor(self.main_display)
            self.cursor_hidden = True

    def show_cursor(self):
        if self.cursor_hidden:
            Quartz.CGDisplayShowCursor(self.main_display)
            self.cursor_hidden = False

    # ---------- event injection ----------

    def post_button(self, button, action):
        btn_map = {'left': 0, 'right': 1, 'middle': 2}
        btn = btn_map.get(button, 0)
        loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        if btn == 0:
            et = (Quartz.kCGEventLeftMouseDown if action == 'down'
                  else Quartz.kCGEventLeftMouseUp)
        elif btn == 1:
            et = (Quartz.kCGEventRightMouseDown if action == 'down'
                  else Quartz.kCGEventRightMouseUp)
        else:
            et = (Quartz.kCGEventOtherMouseDown if action == 'down'
                  else Quartz.kCGEventOtherMouseUp)
        evt = Quartz.CGEventCreateMouseEvent(None, et, loc, btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    def post_scroll(self, dx, dy):
        if dy:
            evt = Quartz.CGEventCreateScrollWheelEvent(
                None, Quartz.kCGScrollEventUnitLine, 1, int(dy)
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        if dx:
            evt = Quartz.CGEventCreateScrollWheelEvent(
                None, Quartz.kCGScrollEventUnitLine, 2, 0, int(dx)
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)

    # ---------- message handling ----------

    def handle(self, msg):
        t = msg.get('type')
        if t == 'enter':
            self.show_cursor()
            self.warp(msg.get('x', self.screen_w - 1),
                      msg.get('y', self.screen_h // 2))
        elif t == 'leave':
            self.hide_cursor()
        elif t == 'move':
            self.warp(msg['x'], msg['y'])
        elif t == 'button':
            self.post_button(msg['button'], msg['action'])
        elif t == 'scroll':
            self.post_scroll(msg.get('dx', 0), msg.get('dy', 0))
        elif t == 'clipboard':
            text = msg.get('text', '')
            if text and text != self.last_clipboard:
                self.last_clipboard = text
                pyperclip.copy(text)
                print(f"[←] Clipboard from host: {text[:40]!r}")

    # ---------- loops ----------

    def connect_loop(self):
        while not self.stop.is_set():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.connect((self.host, self.port))
                self.sock = s
                self.connected = True
                self.last_clipboard = pyperclip.paste()
                print(f"[+] Connected to {self.host}:{self.port}")
                send_msg(self.sock, {
                    'type': 'hello',
                    'width': self.screen_w,
                    'height': self.screen_h,
                })
                # Курсор по умолчанию спрятан — управление на хосте
                self.hide_cursor()
                self.rx_loop()
            except Exception as e:
                print(f"[!] Connection error: {e}")
            finally:
                self.connected = False
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
                self.hide_cursor()
            if not self.stop.is_set():
                print("[*] Reconnecting in 2s...")
                time.sleep(2.0)

    def rx_loop(self):
        while not self.stop.is_set() and self.connected:
            try:
                msg = recv_msg(self.sock)
            except Exception as e:
                print(f"[!] RX error: {e}")
                break
            if msg is None:
                break
            self.handle(msg)

    def clipboard_loop(self):
        while not self.stop.is_set():
            if self.connected and self.sock:
                try:
                    cur = pyperclip.paste()
                    if cur and cur != self.last_clipboard:
                        self.last_clipboard = cur
                        send_msg(self.sock, {'type': 'clipboard', 'text': cur})
                        print(f"[→] Clipboard to host: {cur[:40]!r}")
                except Exception:
                    pass
            time.sleep(1.0)

    def heartbeat_loop(self):
        """Раз в секунду шлём ping, чтобы хост не считал нас мёртвыми."""
        while not self.stop.is_set():
            if self.connected and self.sock:
                try:
                    send_msg(self.sock, {'type': 'ping'})
                except Exception:
                    pass
            time.sleep(1.0)

    def run(self):
        threading.Thread(target=self.clipboard_loop, daemon=True).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        self.connect_loop()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python client_macos.py <host_ip> [port]")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    try:
        ClientApp(host, port).run()
    except KeyboardInterrupt:
        print("\n[*] Bye")