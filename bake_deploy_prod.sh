#!/bin/bash
set -e # Exit on error

uv run unmute/scripts/check_hugging_face_token_not_write.py $HUGGING_FACE_HUB_TOKEN

expected_branch="prod"

current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "$expected_branch" ]]; then
  echo "❌ You are on branch '$current_branch'. Please switch to '$expected_branch' before deploying."
  read -p "Continue anyway? [y/N]: " override
  if [[ ! "$override" =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

if [[ -n $(git status --porcelain) ]]; then
  echo "❌ You have uncommitted changes. Please commit or stash them before deploying."
  read -p "Continue anyway? [y/N]: " override
  if [[ ! "$override" =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

set -x # Print commands

export DOMAIN=unmute.sh
export KYUTAI_LLM_MODEL=google/gemma-3-12b-it
export DOCKER_HOST=ssh://root@${DOMAIN}

echo "If you get an connection error, do: ssh root@${DOMAIN}"

docker buildx bake -f ./swarm-deploy.yml --allow=ssh --push
docker stack deploy --with-registry-auth --prune --compose-file ./swarm-deploy.yml llm-wrapper
