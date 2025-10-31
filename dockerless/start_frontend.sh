#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

cd frontend
pnpm install
pnpm env use --global lts
pnpm dev
