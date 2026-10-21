#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

HOST_IP="${1:-192.168.0.143}"
PORT="${2:-6000}"

echo "Starting KVM Client on macOS connecting to ${HOST_IP}:${PORT}..."
export PYTHONPATH="$DIR/src"
"$DIR/.venv/bin/python" -m buftogether.client "$HOST_IP" --port "$PORT"
