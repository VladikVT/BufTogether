# test_warp.py — запускать на macOS, БЕЗ хоста
import time, Quartz

d = Quartz.CGMainDisplayID()
b = Quartz.CGDisplayBounds(d)
W, H = int(b.size.width), int(b.size.height)

for hz, secs in [(60, 5), (200, 5), (500, 5)]:
    print(f"--- {hz} Hz for {secs}s ---")
    period = 1.0 / hz
    t0 = time.time()
    i = 0
    while time.time() - t0 < secs:
        x = W // 2 + int((W // 3) * ((i % 60) / 60 - 0.5))
        Quartz.CGWarpMouseCursorPosition((float(x), float(H // 2)))
        i += 1
        time.sleep(period)
    print(f"sent {i} warps")