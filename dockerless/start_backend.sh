#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

export UNMUTE_CORS_ALLOW_ORIGINS="https://xzso00wrvev0el-3000.proxy.runpod.net/"

uv run uvicorn unmute.main_websocket:app --reload --host 0.0.0.0 --port 8000 --ws-per-message-deflate=false
