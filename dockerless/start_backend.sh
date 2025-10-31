#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

uv run uvicorn unmute.main_websocket:app --reload --host 0.0.0.0 --port 8000 --ws-per-message-deflate=false
