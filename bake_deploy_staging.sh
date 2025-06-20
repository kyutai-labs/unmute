#!/bin/bash
set -ex

export DOMAIN=unmute-staging.kyutai.io
export KYUTAI_LLM_MODEL=google/gemma-3-1b-it
export DOCKER_HOST=ssh://root@${DOMAIN}

echo "If you get an connection error, do: ssh root@${DOMAIN}"

docker buildx bake -f ./swarm-deploy.yml --allow=ssh --push
docker stack deploy --with-registry-auth --prune --compose-file ./swarm-deploy.yml llm-wrapper
docker service scale -d llm-wrapper_tts=1 llm-wrapper_llm=1
