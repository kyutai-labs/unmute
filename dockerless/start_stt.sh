#!/bin/bash
set -ex
cd "$(dirname "$0")/.."


# We need libpython because the TTS uses a Python component. STT and TTS have the same executable, so we need
# to have libpython even if we don't end up using it. For simplicity, we use the same code as for TTS, even though
# you don't need to install any of these Python packages if you're only using the STT.
uv venv
source .venv/bin/activate
export LD_LIBRARY_PATH=$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

cargo install --features cuda moshi-server@0.6.4
moshi-server worker --config services/moshi-server/configs/stt.toml --port 8090
