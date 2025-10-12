#!/bin/bash
# Script to fix common CUDA issues with Unmute

set -e

echo "🔧 CUDA Issue Fix Script for Unmute"
echo "===================================="

# Check if running as root for some operations
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Some operations require sudo privileges"
        echo "   Run with: sudo $0"
        echo "   Or run individual commands with sudo as needed"
    fi
}

# Function to install NVIDIA Container Toolkit
install_nvidia_container_toolkit() {
    echo "📦 Installing NVIDIA Container Toolkit..."
    
    # Add NVIDIA package repository
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    sudo apt update
    sudo apt install -y nvidia-container-toolkit
    
    # Configure Docker runtime
    sudo nvidia-ctk runtime configure --runtime=docker
    
    echo "✅ NVIDIA Container Toolkit installed"
}

# Function to configure Docker daemon
configure_docker_daemon() {
    echo "🐳 Configuring Docker daemon..."
    
    # Create daemon.json if it doesn't exist
    if [ ! -f /etc/docker/daemon.json ]; then
        sudo mkdir -p /etc/docker
        echo '{}' | sudo tee /etc/docker/daemon.json > /dev/null
    fi
    
    # Backup existing config
    sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.backup
    
    # Create new config with NVIDIA runtime
    cat << 'EOF' | sudo tee /etc/docker/daemon.json > /dev/null
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-runtime": "runc"
}
EOF
    
    echo "✅ Docker daemon configured"
}

# Function to restart Docker
restart_docker() {
    echo "🔄 Restarting Docker..."
    sudo systemctl restart docker
    
    # Wait for Docker to start
    sleep 5
    
    if sudo systemctl is-active --quiet docker; then
        echo "✅ Docker restarted successfully"
    else
        echo "❌ Docker failed to restart"
        return 1
    fi
}

# Function to test GPU access
test_gpu_access() {
    echo "🧪 Testing GPU access..."
    
    # Test nvidia-smi
    if nvidia-smi > /dev/null 2>&1; then
        echo "✅ nvidia-smi works"
    else
        echo "❌ nvidia-smi failed"
        echo "   Install NVIDIA drivers: sudo apt install nvidia-driver-535"
        return 1
    fi
    
    # Test Docker GPU access
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi > /dev/null 2>&1; then
        echo "✅ Docker GPU access works"
        return 0
    else
        echo "❌ Docker GPU access failed"
        return 1
    fi
}

# Function to show current status
show_status() {
    echo "📊 Current Status"
    echo "=================="
    
    # NVIDIA driver
    if nvidia-smi > /dev/null 2>&1; then
        echo "✅ NVIDIA Driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
    else
        echo "❌ NVIDIA Driver: Not working"
    fi
    
    # NVIDIA Container Toolkit
    if which nvidia-container-runtime > /dev/null 2>&1; then
        echo "✅ NVIDIA Container Toolkit: Installed"
    else
        echo "❌ NVIDIA Container Toolkit: Not installed"
    fi
    
    # Docker
    if systemctl is-active --quiet docker; then
        echo "✅ Docker: Running"
    else
        echo "❌ Docker: Not running"
    fi
    
    # Docker GPU test
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi > /dev/null 2>&1; then
        echo "✅ Docker GPU Access: Working"
    else
        echo "❌ Docker GPU Access: Failed"
    fi
}

# Main menu
main_menu() {
    echo ""
    echo "🛠️  What would you like to do?"
    echo "1. Show current status"
    echo "2. Install NVIDIA Container Toolkit"
    echo "3. Configure Docker daemon"
    echo "4. Restart Docker"
    echo "5. Test GPU access"
    echo "6. Full automatic fix"
    echo "7. Use CPU-only mode"
    echo "8. Exit"
    echo ""
    read -p "Choose option (1-8): " choice
    
    case $choice in
        1)
            show_status
            main_menu
            ;;
        2)
            install_nvidia_container_toolkit
            main_menu
            ;;
        3)
            configure_docker_daemon
            main_menu
            ;;
        4)
            restart_docker
            main_menu
            ;;
        5)
            test_gpu_access
            main_menu
            ;;
        6)
            echo "🚀 Running full automatic fix..."
            install_nvidia_container_toolkit
            configure_docker_daemon
            restart_docker
            test_gpu_access
            echo "✅ Automatic fix complete!"
            main_menu
            ;;
        7)
            echo "💻 Switching to CPU-only mode..."
            echo ""
            echo "Use this command to start CPU-only backend:"
            echo "docker compose -f docker-compose.cpu-only.yml up --build"
            echo ""
            echo "Note: This will use a much smaller LLM and no STT/TTS"
            echo "You'll need to modify the backend to handle missing services"
            ;;
        8)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid option"
            main_menu
            ;;
    esac
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check if NVIDIA GPU exists
if ! lspci | grep -i nvidia > /dev/null; then
    echo "❌ No NVIDIA GPU detected"
    echo "   This system may not have an NVIDIA GPU"
    echo "   Consider using CPU-only mode"
    exit 1
fi

echo "✅ NVIDIA GPU detected"

# Check if Docker is installed
if ! which docker > /dev/null; then
    echo "❌ Docker not installed"
    echo "   Install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi

echo "✅ Docker installed"

# Show initial status
show_status

# Start main menu
main_menu