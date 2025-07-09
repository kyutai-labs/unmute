# Speech-IO Kubernetes Deployment

<!-- Testing path exclusions - this change should not trigger Docker Build -->

This directory contains Kubernetes manifests for deploying the Speech-IO application stack, including TTS (Text-to-Speech), STT (Speech-to-Text), backend, and frontend services.

## Prerequisites

- Kubernetes cluster with at least one GPU-enabled node
- [Longhorn](https://longhorn.io/) storage system installed
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/overview.html) installed for GPU support
- kubectl configured to access your cluster
- Ingress controller (e.g., nginx-ingress) for external access
- Access to GitHub Container Registry (GHCR) images (automatically built via CI/CD)
- Git repository with remote origin configured (for dynamic image naming)

## Architecture

The deployment consists of:
- **TTS Service**: Moshi-based text-to-speech service (requires GPU)
- **STT Service**: Moshi-based speech-to-text service (requires GPU)
- **Backend**: API backend service that orchestrates TTS/STT
- **Frontend**: React-based web interface
- **Storage**: Longhorn persistent volumes for caches, models, and logs

All Docker images are automatically built and pushed to GitHub Container Registry (GHCR) via GitHub Actions when code is pushed to the repository. The image names are dynamically determined based on the repository owner, making this deployment work with any fork of the project.

## Quick Start

1. **Update secrets** with your API tokens:
   ```bash
   # HuggingFace token for model downloads
   kubectl -n speech-io create secret generic huggingface-token \
     --from-literal=token=YOUR_HUGGINGFACE_TOKEN

   # NewsAPI token for backend
   kubectl -n speech-io create secret generic newsapi-token \
     --from-literal=token=YOUR_NEWSAPI_TOKEN
   ```

2. **Deploy everything**:
   ```bash
   ./deploy.sh
   ```

   The deployment script automatically detects your repository owner and updates image references accordingly.

3. **Access the application**:
   - Add `127.0.0.1 speech-io.local` to your `/etc/hosts` file
   - Visit http://speech-io.local

## Manual Deployment

If you prefer to deploy manually:

```bash
# Set your kubeconfig
export KUBECONFIG=/home/lukes/nix-configs/machine-profiles/assets/.kube/config

# Update image references for your repository
./update-images.sh

# Deploy in order
kubectl apply -f namespace-and-storage.yaml
kubectl apply -f secrets.yaml  # Update tokens first!
kubectl apply -f tts.yaml
kubectl apply -f stt.yaml
kubectl apply -f backend.yaml
kubectl apply -f frontend.yaml
```

## Storage Configuration

The deployment uses Longhorn storage with the following persistent volumes:

| Volume | Size | Purpose |
|--------|------|---------|
| `cargo-registry-tts` | 5Gi | Rust cargo registry cache for TTS |
| `cargo-registry-stt` | 5Gi | Rust cargo registry cache for STT |
| `tts-target` | 10Gi | TTS build artifacts |
| `stt-target` | 10Gi | STT build artifacts |
| `uv-cache` | 5Gi | Python UV cache (shared) |
| `models` | 50Gi | ML models storage (shared) |
| `tts-logs` | 2Gi | TTS service logs |
| `stt-logs` | 2Gi | STT service logs |

## GPU Requirements

Both TTS and STT services require NVIDIA GPUs:
- Each service requests 1 GPU
- Services are scheduled on nodes with `accelerator: nvidia-tesla-gpu` label
- Ensure your GPU nodes have this label or update the `nodeSelector` in the YAML files

## Networking

- **Frontend**: Exposed on port 3000
- **Backend**: Exposed on port 80 with `/api` prefix
- **TTS/STT**: Internal services on port 8080
- **Ingress**: Routes external traffic to frontend and backend

## Monitoring

Check deployment status:
```bash
kubectl -n speech-io get pods
kubectl -n speech-io get services
kubectl -n speech-io get pvc
kubectl -n speech-io logs -f deployment/tts
kubectl -n speech-io logs -f deployment/stt
```

## Troubleshooting

### Image Pull Issues
- Images are automatically built and pushed to GHCR via GitHub Actions
- Ensure the latest images are available: `docker pull ghcr.io/YOUR_USERNAME/unmute-backend:latest`
- Check if images are public or if you need authentication to GHCR
- Run `./update-images.sh` to ensure image names match your repository

### GPU Issues
- Verify GPU operator is installed: `kubectl get nodes -o jsonpath='{.items[*].status.allocatable}' | grep nvidia.com/gpu`
- Check node labels: `kubectl get nodes --show-labels | grep nvidia`

### Storage Issues
- Verify Longhorn is running: `kubectl -n longhorn-system get pods`
- Check storage class: `kubectl get storageclass longhorn`

### Model Download Issues
- Ensure HuggingFace token is valid and has access to required models
- Check TTS/STT logs for download progress: `kubectl -n speech-io logs deployment/tts`

### Networking Issues
- Verify ingress controller is running
- Check ingress status: `kubectl -n speech-io get ingress`
- Ensure `/etc/hosts` entry exists for `speech-io.local`

## Configuration

### Dynamic Image Naming
The deployment automatically detects your repository owner and updates image references. This works for any fork of the project.

**Manual Image Updates:**
```bash
# Update all image references to match your repository
./update-images.sh
```

**Using Custom Images:**
If you want to use custom-built images instead of the GHCR ones, manually update the image references in the deployment files:

```yaml
image: your-registry/unmute-backend:latest
```

### Changing GPU Node Selector
If your GPU nodes have different labels, update the `nodeSelector` in `tts.yaml` and `stt.yaml`:

```yaml
nodeSelector:
  your-gpu-label: your-gpu-value
```

### Adjusting Resource Limits
Update resource requests/limits in the deployment files based on your cluster capacity:

```yaml
resources:
  requests:
    nvidia.com/gpu: 1
    memory: 4Gi
  limits:
    nvidia.com/gpu: 1
    memory: 8Gi
```

## Cleanup

To remove the entire deployment:
```bash
kubectl delete namespace speech-io
```

This will remove all resources and persistent volumes in the namespace.