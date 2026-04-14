#!/bin/bash
# This is the Kyutai-internal version.
set -ex

export LD_LIBRARY_PATH=$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')

uvx --from 'huggingface_hub[cli]' hf auth login --token $HUGGING_FACE_HUB_TOKEN

cargo run --features=cuda --bin=moshi-server -r -- $@
