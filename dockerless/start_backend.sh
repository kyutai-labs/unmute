#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

UVICORN_ARGS="--reload --host 0.0.0.0 --port 8000 --ws-per-message-deflate=false"

if [[ -n "$SSL_KEYFILE" && -n "$SSL_CERTFILE" ]]; then
    UVICORN_ARGS="$UVICORN_ARGS --ssl-keyfile $SSL_KEYFILE --ssl-certfile $SSL_CERTFILE"
fi

uv run uvicorn unmute.main_websocket:app $UVICORN_ARGS