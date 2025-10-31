#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

export NEXT_PUBLIC_BACKEND_SERVER_URL="https://xzso00wrvev0el-8000.proxy.runpod.net/"

cd frontend
pnpm install
pnpm env use --global lts
pnpm dev
