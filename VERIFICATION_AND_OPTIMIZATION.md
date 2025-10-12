# Audio Flow Verification & VRAM Optimization Guide

## 🔄 What Happens After Backend Connects

### Connection Flow
1. **Backend initiates connection** to remote device WebSocket server
2. **Session configuration** sent (voice, instructions, settings)
3. **Audio processing loop** begins:
   ```
   Device Mic → Opus → WebSocket → Backend STT → LLM → TTS → Opus → WebSocket → Device Speakers
   ```

### Conversation Cycle
1. **Continuous audio capture** from device microphone
2. **Voice Activity Detection (VAD)** detects speech start/end
3. **Speech-to-Text** transcribes user speech
4. **LLM generates** response based on conversation context
5. **Text-to-Speech** synthesizes audio response
6. **Audio playback** through device speakers
7. **Cycle repeats** for ongoing conversation

## 🔍 Verifying Audio Flow

### 1. Quick Status Check
```bash
# Check device connections
curl http://localhost:8000/v1/devices/status

# Expected response:
{
  "devices": {
    "device_name": {
      "connected": true,
      "device_host": "192.168.1.100",
      "device_port": 8765,
      "voice": "Watercooler"
    }
  },
  "summary": {
    "total": 1,
    "enabled": 1,
    "connected": 1
  }
}
```

### 2. Monitor Audio Activity
```bash
# Run the audio flow monitor
python monitor_audio_flow.py

# Or check container logs
docker compose -f docker-compose.autoconnect.yml logs -f backend-autoconnect
```

### 3. Remote Device Verification
On your remote device, you should see:
```
INFO - Backend connected from ('192.168.1.xxx', xxxxx)
INFO - Session configured: {'voice': 'Watercooler', 'instructions': {...}}
INFO - Starting audio capture loop
```

### 4. Backend Log Indicators
Look for these messages in backend logs:
```
INFO - Connected to device_name
DEBUG - Received from device_name: input_audio_buffer.append
DEBUG - Emitting: response.audio.delta
```

### 5. Audio Quality Indicators
- **Device side**: Opus encoding/decoding activity
- **Backend side**: STT transcription events, TTS synthesis events
- **Network**: Consistent WebSocket message flow
- **Audio**: Clear speech recognition and response playback

## 🎤 Testing Audio Flow

### Interactive Test
```bash
# 1. Start monitoring
python monitor_audio_flow.py

# 2. On remote device, speak clearly:
"Hello, can you hear me?"

# 3. Expected flow:
# - Device captures and sends audio
# - Backend processes speech
# - STT produces transcription
# - LLM generates response
# - TTS synthesizes audio
# - Device plays response

# 4. Check logs for activity
docker compose logs backend-autoconnect | grep -E "(audio|speech|response)"
```

### Debug Mode
Enable verbose logging by setting environment variable:
```bash
# In docker-compose.autoconnect.yml
environment:
  - LOG_LEVEL=debug
```

## 🚀 VRAM Optimization Solutions

### Current Memory Usage (Typical)
- **STT Service**: ~1-2 GB VRAM
- **TTS Service**: ~2-3 GB VRAM  
- **LLM Service**: ~2-4 GB VRAM
- **Total**: ~5-9 GB VRAM

### 1. Use Low-Memory Configuration
```bash
# Use optimized Docker Compose
docker compose -f docker-compose.lowmem.yml up --build
```

### 2. LLM Model Optimization

#### Smaller Models
```yaml
# In docker-compose.lowmem.yml - LLM service
command:
  [
    # Ultra-small model (~300MB)
    "--model=distilgpt2",
    
    # Small conversational model (~500MB)  
    "--model=microsoft/DialoGPT-small",
    
    # Tiny instruction model (~1GB)
    "--model=TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  ]
```

#### Memory Settings
```yaml
command:
  [
    "--model=meta-llama/Llama-3.2-1B-Instruct",
    "--max-model-len=512",           # Reduce context (was 1536)
    "--dtype=float16",               # Use half precision
    "--gpu-memory-utilization=0.15", # Reduce GPU usage (was 0.4)
    "--cpu-offload-gb=2",           # Offload to CPU
    "--max-num-seqs=2"              # Reduce batch size
  ]
```

### 3. Service-Level Optimizations

#### Environment Variables
```yaml
environment:
  # Reduce CUDA memory fragmentation
  - PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
  
  # Limit to specific GPU
  - CUDA_VISIBLE_DEVICES=0
  
  # Reduce PyTorch memory usage
  - PYTORCH_CUDA_ALLOC_CONF=garbage_collection_threshold:0.6
```

#### Resource Limits
```yaml
deploy:
  resources:
    limits:
      memory: 4G        # Limit system RAM
    reservations:
      devices:
        - driver: nvidia
          count: 1       # Use only 1 GPU
          capabilities: [gpu]
```

### 4. Advanced Optimizations

#### Model Quantization
```bash
# Use quantized models (requires model conversion)
--quantization=int8    # 8-bit quantization
--quantization=int4    # 4-bit quantization (experimental)
```

#### Sequential Loading
```bash
# Load models one at a time instead of all at once
# Start STT first, then TTS, then LLM
docker compose up stt
sleep 30
docker compose up tts  
sleep 30
docker compose up llm backend-autoconnect
```

#### GPU Memory Monitoring
```bash
# Monitor GPU usage
python check_gpu_memory.py

# Watch memory in real-time
watch -n 1 nvidia-smi
```

## 📊 Memory Usage Comparison

| Configuration | STT | TTS | LLM | Total | Quality |
|---------------|-----|-----|-----|-------|---------|
| **Default** | 2GB | 3GB | 4GB | 9GB | Excellent |
| **Optimized** | 1GB | 2GB | 2GB | 5GB | Very Good |
| **Low Memory** | 1GB | 1GB | 1GB | 3GB | Good |
| **Minimal** | 0.5GB | 0.5GB | 0.5GB | 1.5GB | Basic |

## 🛠️ Troubleshooting Audio Issues

### No Audio Received
```bash
# Check device connection
curl http://localhost:8000/v1/devices/status

# Check device server logs
python remote_device_server.py --no-audio  # Test without audio

# Check microphone permissions
# On device: ensure microphone access is granted
```

### Audio Choppy/Delayed
```bash
# Check network latency
ping DEVICE_IP

# Reduce audio chunk size in remote_device_server.py
chunk_size = 960  # 40ms instead of 80ms

# Check GPU memory pressure
python check_gpu_memory.py
```

### STT Not Working
```bash
# Check STT service logs
docker compose logs stt

# Verify audio format
# Ensure 24kHz, mono, float32 format

# Test with known good audio file
```

### TTS Not Working  
```bash
# Check TTS service logs
docker compose logs tts

# Verify voice configuration
curl http://localhost:8000/v1/devices

# Test with simple text
```

## 🎯 Recommended Configurations

### For 8GB GPU
```bash
# Use default configuration with small optimizations
docker compose -f docker-compose.autoconnect.yml up
```

### For 6GB GPU
```bash
# Use low-memory configuration
docker compose -f docker-compose.lowmem.yml up
```

### For 4GB GPU
```bash
# Use minimal model configuration
# Edit docker-compose.lowmem.yml:
# - Use distilgpt2 model
# - Set gpu-memory-utilization=0.1
# - Enable CPU offloading
```

### For Multiple GPUs
```yaml
# Distribute services across GPUs
stt:
  environment:
    - CUDA_VISIBLE_DEVICES=0
tts:
  environment:
    - CUDA_VISIBLE_DEVICES=1  
llm:
  environment:
    - CUDA_VISIBLE_DEVICES=2
```

## 📈 Performance Monitoring

### Real-time Monitoring
```bash
# GPU usage
watch -n 1 nvidia-smi

# Container resources  
docker stats

# Audio flow
python monitor_audio_flow.py
```

### Metrics Collection
```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Health status
curl http://localhost:8000/v1/health
```

This guide should help you verify that audio is flowing correctly and optimize VRAM usage for your specific hardware configuration.