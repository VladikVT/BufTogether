"""Общий протокол: 4 байта длины (big-endian) + JSON."""
import json
import struct


def send_msg(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(struct.pack('!I', len(data)))
    sock.sendall(data)


def recv_msg(sock):
    raw = b''
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            return None
        raw += chunk
    (length,) = struct.unpack('!I', raw)
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    return json.loads(data.decode('utf-8'))