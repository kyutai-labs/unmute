#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

cargo install --features cuda moshi-server@0.6.4
moshi-server worker --config services/moshi-server/configs/stt.toml --port 8090
