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

# Environment configuration
STAGING_DOMAIN="staging.uncensored.ai"
GPU_NODE_NAME="cloud-accelerator-0"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}Starting Speech-IO Kubernetes deployment...${NC}"

# Update image references to match the current repository
echo -e "${GREEN}Updating image references...${NC}"
if [ -f "$SCRIPT_DIR/update-images.sh" ]; then
    "$SCRIPT_DIR/update-images.sh"
else
    echo -e "${YELLOW}Warning: update-images.sh not found, using existing image references.${NC}"
fi

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

# Check if GPU node is available and ready
echo -e "${GREEN}Checking GPU node availability...${NC}"
if ! kubectl get node -l nvidia.com/gpu.present=true | grep -q Ready; then
    echo -e "${RED}Error: No GPU nodes found or GPU node not ready. Please check GPU node status.${NC}"
    exit 1
fi

# Check if NVIDIA GPU resources are available
if ! kubectl get nodes -o jsonpath='{.items[*].status.allocatable}' | grep -q "nvidia.com/gpu"; then
    echo -e "${RED}Error: No NVIDIA GPU resources found. Make sure NVIDIA device plugin is installed.${NC}"
    exit 1
fi

# Check GPU node taint configuration
if ! kubectl describe node -l nvidia.com/gpu.present=true | grep -q "nvidia.com/gpu=true:NoSchedule"; then
    echo -e "${YELLOW}Warning: GPU node doesn't have proper taint. GPU workloads may be scheduled on non-GPU nodes.${NC}"
fi

echo -e "${GREEN}Deploying namespace and storage...${NC}"
kubectl apply -f namespace-and-storage.yaml

# Copy cert-issuer to speech-io namespace
echo -e "${GREEN}Setting up cert-issuer for speech-io namespace...${NC}"
kubectl get secret cfapi-token -o yaml | sed 's/namespace: default/namespace: speech-io/' | kubectl apply -f -
kubectl get originissuer prod-issuer -o yaml | sed 's/namespace: default/namespace: speech-io/' | kubectl apply -f -

echo -e "${GREEN}Deploying secrets (make sure to update tokens)...${NC}"
kubectl apply -f secrets.yaml

echo -e "${YELLOW}Please update the secrets with your actual tokens:${NC}"
echo "kubectl -n speech-io create secret generic huggingface-token --from-literal=token=YOUR_HUGGINGFACE_TOKEN --dry-run=client -o yaml | kubectl apply -f -"
echo "kubectl -n speech-io create secret generic newsapi-token --from-literal=token=YOUR_NEWSAPI_TOKEN --dry-run=client -o yaml | kubectl apply -f -"

echo -e "${GREEN}Checking certificate issuer status...${NC}"
kubectl wait --for=condition=ready originissuer prod-issuer -n speech-io --timeout=60s || echo -e "${YELLOW}Cert issuer not ready, certificates may not be issued immediately${NC}"

echo -e "${GREEN}Deploying TTS service...${NC}"
kubectl apply -f tts.yaml

echo -e "${GREEN}Deploying STT service...${NC}"
kubectl apply -f stt.yaml

echo -e "${GREEN}Deploying backend service...${NC}"
kubectl apply -f backend.yaml

echo -e "${GREEN}Deploying frontend service...${NC}"
kubectl apply -f frontend.yaml

echo -e "${GREEN}Waiting for deployments to be ready...${NC}"
echo -e "${YELLOW}Note: GPU workloads may take longer to initialize due to model loading...${NC}"
kubectl -n speech-io wait --for=condition=available --timeout=600s deployment/tts || echo -e "${YELLOW}TTS deployment timeout, checking pod status...${NC}"
kubectl -n speech-io wait --for=condition=available --timeout=600s deployment/stt || echo -e "${YELLOW}STT deployment timeout, checking pod status...${NC}"
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/backend || echo -e "${YELLOW}Backend deployment timeout, checking pod status...${NC}"
kubectl -n speech-io wait --for=condition=available --timeout=300s deployment/frontend || echo -e "${YELLOW}Frontend deployment timeout, checking pod status...${NC}"

echo -e "${GREEN}Checking final pod status...${NC}"
kubectl -n speech-io get pods -o wide

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}You can check the status with:${NC}"
echo "kubectl -n speech-io get pods"
echo "kubectl -n speech-io get services"
echo "kubectl -n speech-io get pvc"

echo -e "${YELLOW}To access the application:${NC}"
echo "1. Check if ingress is configured for speech-io.$STAGING_DOMAIN"
echo "2. Visit: https://speech-io.$STAGING_DOMAIN (if ingress is configured)"
echo "3. Or use port-forward: kubectl -n speech-io port-forward svc/frontend 8080:80"
echo "4. GPU workloads (TTS/STT) should be running on: $GPU_NODE_NAME"

echo -e "${GREEN}GPU Resource Usage:${NC}"
kubectl top nodes -l nvidia.com/gpu.present=true || echo -e "${YELLOW}GPU metrics not available${NC}"

echo -e "${GREEN}Done!${NC}"
