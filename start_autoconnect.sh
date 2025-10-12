#!/bin/bash
set -e

# Unmute Auto-Connect Backend Startup Script
# This script starts the auto-connect version of Unmute that connects to remote devices

echo "=== Unmute Auto-Connect Backend Startup ==="

# Check if devices.json exists, create example if not
if [ ! -f "devices.json" ]; then
    echo "Creating example devices.json configuration..."
    cp devices.example.json devices.json
    echo "⚠️  Please edit devices.json with your actual device configurations!"
    echo "   Set 'enabled': true and update host/port for your devices"
    echo ""
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Hugging Face token for model access
HUGGING_FACE_HUB_TOKEN=your_token_here

# Optional: News API key
NEWSAPI_API_KEY=your_newsapi_key_here

# Device configuration file path (optional)
REMOTE_DEVICES_CONFIG=./devices.json
EOF
    echo "⚠️  Please edit .env file with your Hugging Face token!"
    echo ""
fi

# Check Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed or not in PATH"
    exit 1
fi

# Check NVIDIA Docker support
if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
    echo "⚠️  NVIDIA Docker support not detected. GPU acceleration may not work."
    echo "   Install NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/"
fi

echo "Starting Unmute Auto-Connect Backend..."
echo "This will start:"
echo "  - Backend (auto-connect): http://localhost:8000"
echo "  - Speech-to-Text service"
echo "  - Text-to-Speech service" 
echo "  - LLM service"
echo ""

# Build and start services
docker compose -f docker-compose.autoconnect.yml up --build

echo ""
echo "=== Shutdown Complete ==="