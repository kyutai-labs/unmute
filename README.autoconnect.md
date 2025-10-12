# Unmute Auto-Connect Backend

This is a modified version of the Unmute backend that automatically connects to remote devices instead of waiting for client connections. This eliminates the need for the frontend website and enables fully automated voice interactions.

## Quick Start

### 1. Setup Configuration

Copy the example configuration:
```bash
cp devices.example.json devices.json
```

Edit `devices.json` with your actual device information:
```json
{
  "devices": [
    {
      "name": "living_room",
      "host": "192.168.1.100",
      "port": 8765,
      "voice": "Watercooler",
      "instructions": {"type": "smalltalk"},
      "auto_reconnect": true,
      "reconnect_delay": 5.0,
      "enabled": true
    }
  ]
}
```

### 2. Setup Environment

Create `.env` file:
```bash
HUGGING_FACE_HUB_TOKEN=your_token_here
REMOTE_DEVICES_CONFIG=./devices.json
```

### 3. Start Backend

Using Docker Compose (recommended):
```bash
docker compose -f docker-compose.autoconnect.yml up --build
```

Or using the startup script:
```bash
./start_autoconnect.sh
```

### 4. Start Remote Device

On your remote device, run:
```bash
# Install dependencies
pip install websockets pyaudio numpy sphn

# Start device server
python remote_device_server.py --host 0.0.0.0 --port 8765
```

## Architecture

```
Backend Container ──WebSocket──> Remote Device (192.168.1.100:8765)
     │                              │
     ├─ STT Service                 ├─ Microphone
     ├─ TTS Service                 ├─ Speakers  
     └─ LLM Service                 └─ WebSocket Server
```

## Configuration Options

### Device Configuration (`devices.json`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique device identifier |
| `host` | string | IP address or hostname |
| `port` | integer | WebSocket port (default: 8765) |
| `voice` | string | Voice name from voices.yaml |
| `instructions` | object | System prompt configuration |
| `auto_reconnect` | boolean | Enable auto-reconnection |
| `reconnect_delay` | float | Seconds to wait before reconnecting |
| `enabled` | boolean | Whether device is active |

### Voice Options

Available voices (from `voices.yaml`):
- `Watercooler` - Casual conversation
- `Gertrude` - Life advice, kind and sympathetic
- `Dev (news)` - News and explanations
- `Charles` - French/English, historical perspective
- `Développeuse` - French conversation
- `Fabieng` - French startup coach

### Instruction Types

| Type | Description |
|------|-------------|
| `smalltalk` | Casual conversation |
| `quiz_show` | Interactive quiz format |
| `news` | News and current events |
| `unmute_explanation` | Technical explanations |
| `constant` | Custom system prompt via `text` field |

## API Endpoints

The auto-connect backend provides these endpoints:

- `GET /` - Service information
- `GET /v1/health` - Health check with device status
- `GET /v1/devices` - List all configured devices
- `GET /v1/devices/status` - Detailed connection status
- `POST /v1/devices/{name}/reconnect` - Manually reconnect device
- `GET /v1/config/example` - Get example configuration
- `GET /metrics` - Prometheus metrics

## Monitoring

### Health Check
```bash
curl http://localhost:8000/v1/health
```

### Device Status
```bash
curl http://localhost:8000/v1/devices/status
```

### Logs
```bash
# View backend logs
docker compose -f docker-compose.autoconnect.yml logs backend-autoconnect

# Follow logs in real-time
docker compose -f docker-compose.autoconnect.yml logs -f backend-autoconnect
```

## Remote Device Server

The `remote_device_server.py` script creates a WebSocket server that:

1. **Accepts connections** from the Unmute backend
2. **Captures audio** from the local microphone
3. **Sends audio** to backend via WebSocket (Opus-encoded)
4. **Receives responses** from backend (audio + text)
5. **Plays audio** through local speakers

### Usage

```bash
# Basic usage
python remote_device_server.py

# Custom host/port
python remote_device_server.py --host 0.0.0.0 --port 8765

# Disable audio (testing only)
python remote_device_server.py --no-audio
```

### Dependencies

```bash
pip install websockets pyaudio numpy sphn
```

Note: On some systems you may need to install PortAudio:
```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# macOS
brew install portaudio

# Windows
# PyAudio wheels usually include PortAudio
```

## Docker Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REMOTE_DEVICES_CONFIG` | Path to devices.json | `/app/devices.json` |
| `HUGGING_FACE_HUB_TOKEN` | HF token for models | Required |
| `HOST` | Backend bind address | `0.0.0.0` |
| `PORT` | Backend port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |

### Volume Mounts

- `./devices.json:/app/devices.json:ro` - Device configuration (read-only)
- `./volumes/backend-logs:/app/logs` - Log files
- `./volumes/hf-cache:/root/.cache/huggingface` - Model cache

### Network Requirements

The backend container needs to reach your remote devices:
- Ensure devices are on accessible network
- Check firewall rules allow connections
- Use `host.docker.internal` for localhost devices on Docker Desktop

## Troubleshooting

### Backend Won't Start
```bash
# Check configuration
docker compose -f docker-compose.autoconnect.yml config

# Check logs
docker compose -f docker-compose.autoconnect.yml logs backend-autoconnect
```

### Device Connection Issues
```bash
# Test device connectivity
curl http://localhost:8000/v1/devices/status

# Check if device server is running
telnet DEVICE_IP 8765

# Test WebSocket connection
wscat -c ws://DEVICE_IP:8765 -s realtime
```

### Audio Issues on Remote Device
```bash
# List audio devices
python -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)}') for i in range(p.get_device_count())]"

# Test microphone
python remote_device_server.py --no-audio  # Should work without audio
```

### GPU/CUDA Issues
```bash
# Test NVIDIA Docker
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Check GPU memory
nvidia-smi
```

## Production Deployment

### Security Considerations

1. **Network Security**: Use VPN or secure network for device connections
2. **Authentication**: Consider adding authentication to device connections
3. **Encryption**: Use WSS (secure WebSocket) for production
4. **Firewall**: Restrict access to necessary ports only

### Scaling

- **Multiple Devices**: The backend supports multiple simultaneous device connections
- **Load Balancing**: Use multiple backend instances with a load balancer
- **Resource Limits**: Set appropriate Docker resource limits
- **Monitoring**: Use Prometheus/Grafana for production monitoring

### Example Production Setup

```yaml
# docker-compose.prod.yml
services:
  backend-autoconnect:
    # ... base configuration
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 4G
          cpus: '2'
    environment:
      - LOG_LEVEL=warning
      - REMOTE_DEVICES_CONFIG=/config/devices.json
    volumes:
      - /secure/path/devices.json:/config/devices.json:ro
```

## Development

### Adding New Features

1. **Device Types**: Extend `RemoteDevice` model in `remote_devices.py`
2. **Connection Logic**: Modify `DeviceConnection` in `device_manager.py`
3. **API Endpoints**: Add routes in `main_auto_connect.py`

### Testing

```bash
# Test with mock devices
python remote_device_server.py --no-audio

# Load testing
# (Adapt existing loadtest_client.py for auto-connect mode)
```

This auto-connect setup provides a robust, scalable solution for deploying voice AI to multiple remote devices without requiring manual connection management.