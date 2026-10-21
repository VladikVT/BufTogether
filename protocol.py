"""
KVM Communication Protocol:
Frame: [ 4 bytes big-endian length ] + [ UTF-8 JSON payload ]
"""
import json
import struct
import socket


def send_msg(sock: socket.socket, obj: dict):
    """Encodes object to JSON and sends in a single network packet."""
    data = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    header = struct.pack('!I', len(data))
    sock.sendall(header + data)


def recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """Reads exactly n bytes from socket, or None if EOF/closed."""
    buf = bytearray(n)
    view = memoryview(buf)
    pos = 0
    while pos < n:
        nbytes = sock.recv_into(view[pos:], n - pos)
        if not nbytes:
            return None
        pos += nbytes
    return bytes(buf)


def recv_msg(sock: socket.socket) -> dict | None:
    """Reads one frame from socket."""
    header = recv_exact(sock, 4)
    if not header:
        return None
    (length,) = struct.unpack('!I', header)
    if length > 16 * 1024 * 1024:  # 16 MB max frame size safety guard
        raise ValueError(f"Frame length too large: {length}")
    payload = recv_exact(sock, length)
    if not payload:
        return None
    return json.loads(payload.decode('utf-8'))
