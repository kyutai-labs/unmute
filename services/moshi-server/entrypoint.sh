#!/usr/bin/env bash
set -euo pipefail

start_script="${1:?missing start script}"
shift

python_env_dir="${MOSHI_PYTHON_ENV_DIR:-python-env}"

exec uv run --locked --project "./${python_env_dir}" "${start_script}" "$@"
