#!/bin/bash
set -e # Exit on error

uv run unmute/scripts/check_hugging_face_token_not_write.py $HUGGING_FACE_HUB_TOKEN

set -x # Print commands

export DOMAIN=unmute.kyutai.org
export KYUTAI_LLM_MODEL=google/gemma-3-12b-it
export DOCKER_HOST=ssh://root@${DOMAIN}

echo "If you get an connection error, do: ssh root@${DOMAIN}"

export KYUTAI_LLM_API_KEY=$OPENROUTER_API_KEY_UNMUTE

docker buildx bake -f ./swarm-deploy.yml --allow=ssh --push
docker stack deploy --with-registry-auth --prune --compose-file ./swarm-deploy.yml llm-wrapper
