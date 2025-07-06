#!/usr/bin/env bash

# Speech-IO Kubernetes Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set kubeconfig
export KUBECONFIG=/home/lukes/nix-configs/machine-profiles/assets/.kube/config

echo -e "${GREEN}Starting Speech-IO Kubernetes deployment...${NC}"

# Check if kubectl is available
if ! command -v kubectl &>/dev/null; then
    echo -e "${RED}kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &>/dev/null; then
    echo -e "${RED}Cannot connect to Kubernetes cluster. Please check your kubeconfig.${NC}"
    exit 1
fi

# Check if Longhorn is installed
if ! kubectl get storageclass longhorn &>/dev/null; then
    echo -e "${YELLOW}Warning: Longhorn storage class not found. Make sure Longhorn is installed.${NC}"
fi

# Check if NVIDIA GPU operator is installed
if ! kubectl get nodes -o jsonpath='{.items[*].status.allocatable}' | grep -q "nvidia.com/gpu"; then
    echo -e "${YELLOW}Warning: No NVIDIA GPU resources found. Make sure NVIDIA GPU operator is installed.${NC}"
fi

echo -e "${GREEN}Deploying namespace and storage...${NC}"
kubectl apply -f namespace-and-storage.yaml

echo -e "${GREEN}Deploying secrets (make sure to update tokens)...${NC}"
kubectl apply -f secrets.yaml

echo -e "${YELLOW}Please update the secrets with your actual tokens:${NC}"
echo "kubectl -n speech-io create secret generic huggingface-token --from-literal=token=YOUR_HUGGINGFACE_TOKEN --dry-run=client -o yaml | kubectl apply -f -"
echo "kubectl -n speech-io create secret generic newsapi-token --from-literal=token=YOUR_NEWSAPI_TOKEN --dry-run=client -o yaml | kubectl apply -f -"

echo -e "${GREEN}Deploying TTS service...${NC}"
kubectl apply -f tts.yaml

echo -e "${GREEN}Deploying STT service...${NC}"
kubectl apply -f stt.yaml

echo -e "${GREEN}Deploying backend service...${NC}"
kubectl apply -f backend.yaml

echo -e "${GREEN}Deploying frontend service...${NC}"
kubectl apply -f frontend.yaml

echo -e "${GREEN}Waiting for deployments to be ready...${NC}"
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/tts
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/stt
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/backend
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/frontend

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}You can check the status with:${NC}"
echo "kubectl -n speech-io get pods"
echo "kubectl -n speech-io get services"
echo "kubectl -n speech-io get pvc"

echo -e "${YELLOW}To access the application:${NC}"
echo "Add '127.0.0.1 speech-io.local' to your /etc/hosts file"
echo "Then visit: http://speech-io.local (make sure you have an ingress controller installed)"

echo -e "${GREEN}Done!${NC}"
