#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

cd frontend
pnpm install
pnpm env use --global lts

PNPM_ARGS=""

if [[ -n "$SSL_KEYFILE" && -n "$SSL_CERTFILE" ]]; then
    PNPM_ARGS="$PNPM_ARGS --experimental-https --experimental-https-key ../$SSL_KEYFILE --experimental-https-cert ../$SSL_CERTFILE"
fi

if [[ -n "$HTTP_HOST" ]]; then
    PNPM_ARGS="$PNPM_ARGS -H $HTTP_HOST"
fi

pnpm dev $PNPM_ARGS