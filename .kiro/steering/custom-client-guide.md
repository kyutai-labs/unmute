# Building a Custom Client for Unmute Backend

## Overview

This guide explains how to create your own client application that connects to the Unmute backend server. You can build clients in any language that supports WebSockets and audio processing.

## Prerequisites

### Server Requirements
- Unmute backend server running (see tech.md for setup)
- Server health endpoint accessible at `/v1/health`
- WebSocket endpoint available at `/v1/realtime`

### Client Requirements
- WebSocket client library
- Audio processing capabilities (Opus codec support recommended)
- Base64 encoding/decoding
- JSON parsing

## Connection Setup

### 1. Health Check
Before connecting, verify the server is healthy:

```python
import requests

def check_server_health(server_url: str):
    health_url = f"{server_url.rstrip('/')}/v1/health"
    response = requests.get(health_url)
    
    if response.status_code != 200:
        raise RuntimeError(f"Server unhealthy: {response.text}")
    
    health = response.json()
    if not health["ok"]:
        raise RuntimeError(f"Services not ready: {health}")
    
    return health
```

### 2. WebSocket Connection
Connect to the realtime endpoint with the required subprotocol:

```python
import websockets
import asyncio

async def connect_to_unmute(server_url: str):
    websocket_url = f"{server_url.rstrip('/')}/v1/realtime"
    
    websocket = await websockets.connect(
        websocket_url,
        subprotocols=[websockets.Subprotocol("realtime")]
    )
    
    print(f"Connected to {websocket_url}")
    return websocket
```

### 3. Session Configuration
Send initial session configuration:

```python
import json

async def configure_session(websocket, voice="Watercooler", instructions=None):
    session_config = {
        "type": "session.update",
        "session": {
            "voice": voice,
            "instructions": instructions or {
                "type": "smalltalk"
            },
            "allow_recording": False
        }
    }
    
    await websocket.send(json.dumps(session_config))
```

## Audio Processing

### Input Audio (Microphone → Server)

#### Option 1: Using Opus Encoding (Recommended)
```python
import sphn
import base64
import numpy as np

class AudioSender:
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate
        self.opus_writer = sphn.OpusStreamWriter(sample_rate)
    
    async def send_audio_chunk(self, websocket, audio_data: np.ndarray):
        """Send audio data as Opus-encoded WebSocket message"""
        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Encode to Opus
        opus_bytes = self.opus_writer.append_pcm(audio_data)
        
        if opus_bytes:  # Opus may not output on every input due to buffering
            # Encode to base64
            audio_b64 = base64.b64encode(opus_bytes).decode('utf-8')
            
            # Send WebSocket message
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            
            await websocket.send(json.dumps(message))
```

#### Option 2: Using Raw PCM (Alternative)
```python
def send_raw_audio(websocket, audio_data: np.ndarray):
    """Send raw PCM audio (less efficient than Opus)"""
    # Convert to 16-bit PCM
    pcm_int16 = (audio_data * 32767).astype(np.int16)
    
    # Encode to base64
    audio_b64 = base64.b64encode(pcm_int16.tobytes()).decode('utf-8')
    
    message = {
        "type": "input_audio_buffer.append",
        "audio": audio_b64
    }
    
    await websocket.send(json.dumps(message))
```

### Output Audio (Server → Client)

```python
class AudioReceiver:
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate
        self.opus_reader = sphn.OpusStreamReader(sample_rate)
        self.audio_chunks = []
    
    def process_audio_message(self, message_data):
        """Process incoming audio delta message"""
        if message_data["type"] == "response.audio.delta":
            # Decode base64 Opus data
            opus_bytes = base64.b64decode(message_data["delta"])
            
            # Decode Opus to PCM
            pcm_data = self.opus_reader.append_bytes(opus_bytes)
            
            if pcm_data.size > 0:
                self.audio_chunks.append(pcm_data)
                return pcm_data
        
        return None
    
    def get_complete_audio(self):
        """Get all received audio as single array"""
        if self.audio_chunks:
            return np.concatenate(self.audio_chunks)
        return np.array([])
```

## Complete Client Examples

### Python Client (Minimal)

```python
import asyncio
import json
import base64
import numpy as np
import websockets
import sphn
from pathlib import Path

class UnmuteClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.websocket = None
        self.opus_writer = sphn.OpusStreamWriter(24000)
        self.opus_reader = sphn.OpusStreamReader(24000)
    
    async def connect(self):
        """Connect to Unmute server"""
        websocket_url = f"{self.server_url.rstrip('/')}/v1/realtime"
        self.websocket = await websockets.connect(
            websocket_url,
            subprotocols=[websockets.Subprotocol("realtime")]
        )
        
        # Configure session
        await self.configure_session()
    
    async def configure_session(self, voice="Watercooler"):
        """Send session configuration"""
        config = {
            "type": "session.update",
            "session": {
                "voice": voice,
                "instructions": {"type": "smalltalk"},
                "allow_recording": False
            }
        }
        await self.websocket.send(json.dumps(config))
    
    async def send_audio_file(self, audio_file_path: Path):
        """Send audio file to server"""
        # Load audio file
        audio_data, sr = sphn.read(audio_file_path, sample_rate=24000)
        if audio_data.ndim > 1:
            audio_data = audio_data[0]  # Take first channel for mono
        
        # Send in chunks
        chunk_size = 1920  # 80ms at 24kHz
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.08)  # 80ms delay between chunks
    
    async def send_audio_chunk(self, audio_data: np.ndarray):
        """Send single audio chunk"""
        opus_bytes = self.opus_writer.append_pcm(audio_data)
        if opus_bytes:
            message = {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(opus_bytes).decode('utf-8')
            }
            await self.websocket.send(json.dumps(message))
    
    async def listen_for_responses(self):
        """Listen for server responses"""
        async for message_raw in self.websocket:
            message = json.loads(message_raw)
            
            if message["type"] == "response.audio.delta":
                # Process audio response
                opus_bytes = base64.b64decode(message["delta"])
                pcm_data = self.opus_reader.append_bytes(opus_bytes)
                if pcm_data.size > 0:
                    print(f"Received {len(pcm_data)} audio samples")
            
            elif message["type"] == "conversation.item.input_audio_transcription.delta":
                # User speech transcription
                print(f"User said: {message['delta']}")
            
            elif message["type"] == "response.text.delta":
                # Assistant text response
                print(f"Assistant: {message['delta']}", end="")
            
            elif message["type"] == "error":
                print(f"Error: {message['error']['message']}")
            
            else:
                print(f"Received: {message['type']}")

# Usage example
async def main():
    client = UnmuteClient("ws://localhost:8000")
    await client.connect()
    
    # Start listening in background
    listen_task = asyncio.create_task(client.listen_for_responses())
    
    # Send audio file
    await client.send_audio_file(Path("test_audio.wav"))
    
    # Wait for responses
    await asyncio.sleep(10)
    listen_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript/Node.js Client

```javascript
const WebSocket = require('ws');
const fs = require('fs');

class UnmuteClient {
    constructor(serverUrl) {
        this.serverUrl = serverUrl;
        this.ws = null;
    }
    
    async connect() {
        const wsUrl = `${this.serverUrl.replace('http', 'ws')}/v1/realtime`;
        
        this.ws = new WebSocket(wsUrl, ['realtime']);
        
        return new Promise((resolve, reject) => {
            this.ws.on('open', () => {
                console.log('Connected to Unmute server');
                this.configureSession();
                resolve();
            });
            
            this.ws.on('error', reject);
        });
    }
    
    configureSession(voice = 'Watercooler') {
        const config = {
            type: 'session.update',
            session: {
                voice: voice,
                instructions: { type: 'smalltalk' },
                allow_recording: false
            }
        };
        
        this.ws.send(JSON.stringify(config));
    }
    
    sendAudioData(audioBase64) {
        const message = {
            type: 'input_audio_buffer.append',
            audio: audioBase64
        };
        
        this.ws.send(JSON.stringify(message));
    }
    
    onMessage(callback) {
        this.ws.on('message', (data) => {
            const message = JSON.parse(data.toString());
            callback(message);
        });
    }
}

// Usage
async function main() {
    const client = new UnmuteClient('ws://localhost:8000');
    await client.connect();
    
    client.onMessage((message) => {
        console.log('Received:', message.type);
        
        if (message.type === 'response.text.delta') {
            process.stdout.write(message.delta);
        }
    });
    
    // Send audio data here...
}
```

## Message Types Reference

### Client → Server Messages

| Type | Purpose | Required Fields |
|------|---------|----------------|
| `session.update` | Configure voice/instructions | `session` |
| `input_audio_buffer.append` | Send audio data | `audio` (base64) |

### Server → Client Messages

| Type | Purpose | Data |
|------|---------|------|
| `session.updated` | Confirm session config | `session` |
| `response.created` | Response generation started | `response` |
| `response.text.delta` | Text response chunk | `delta` |
| `response.audio.delta` | Audio response chunk | `delta` (base64) |
| `response.audio.done` | Audio response complete | - |
| `conversation.item.input_audio_transcription.delta` | User speech transcription | `delta`, `start_time` |
| `input_audio_buffer.speech_started` | Speech detection started | - |
| `input_audio_buffer.speech_stopped` | Speech detection stopped | - |
| `error` | Error occurred | `error.message`, `error.type` |

## Best Practices

### Performance
- Use Opus encoding for audio (much more efficient than raw PCM)
- Send audio in small chunks (20-80ms) for low latency
- Process messages asynchronously to avoid blocking

### Error Handling
- Always check server health before connecting
- Handle WebSocket disconnections gracefully
- Implement retry logic for connection failures
- Monitor for error messages from server

### Audio Quality
- Use 24kHz sample rate for best compatibility
- Ensure mono audio (single channel)
- Normalize audio levels appropriately
- Handle silence detection properly

### Security
- Use WSS (secure WebSocket) for production
- Implement proper authentication if required
- Validate all incoming messages
- Handle user permissions for microphone access

## Testing Your Client

### Basic Connection Test
```bash
# Test server health
curl http://localhost:8000/v1/health

# Test WebSocket connection (using wscat)
npm install -g wscat
wscat -c ws://localhost:8000/v1/realtime -s realtime
```

### Load Testing
Use the provided load test client as reference:
```bash
uv run unmute/loadtest/loadtest_client.py --server-url ws://localhost:8000 --n-workers 1
```

## Troubleshooting

### Common Issues
- **Connection refused**: Check if backend server is running
- **Subprotocol error**: Ensure `realtime` subprotocol is specified
- **Audio not processed**: Verify Opus encoding and base64 format
- **No response**: Check session configuration and voice availability
- **High latency**: Reduce audio chunk size, check GPU memory

### Debug Mode
Enable debug mode in the frontend (press 'D') to see detailed message flow and timing information.