# Auto-Connection Setup: Backend Initiating Connections to Remote Devices

## Overview

This guide explains how to modify the Unmute backend to automatically initiate connections to remote devices with microphones, eliminating the need for the frontend website and manual connection initiation.

## Architecture Change

### Current Flow (Client-Initiated)
```
Remote Device → WebSocket Connect → Backend → Accept Connection
```

### New Flow (Backend-Initiated)
```
Backend → WebSocket Connect → Remote Device → Accept Connection
```

## Implementation Options

### Option 1: Modify Backend to Connect Outbound (Recommended)

Create a new service that connects to remote devices automatically.

#### 1. Create Remote Device Configuration

```python
# unmute/remote_devices.py
from typing import List
from pydantic import BaseModel

class RemoteDevice(BaseModel):
    name: str
    host: str
    port: int
    voice: str = "Watercooler"
    instructions: dict = {"type": "smalltalk"}
    auto_reconnect: bool = True
    reconnect_delay: float = 5.0

class RemoteDevicesConfig(BaseModel):
    devices: List[RemoteDevice]

# Example configuration
DEFAULT_DEVICES = [
    RemoteDevice(
        name="living_room_device",
        host="192.168.1.100",
        port=8765,
        voice="Watercooler"
    ),
    RemoteDevice(
        name="kitchen_device", 
        host="192.168.1.101",
        port=8765,
        voice="Gertrude"
    )
]
```

#### 2. Create Device Connection Manager

```python
# unmute/device_manager.py
import asyncio
import json
import logging
from typing import Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

from unmute.unmute_handler import UnmuteHandler
from unmute.remote_devices import RemoteDevice, RemoteDevicesConfig
import unmute.openai_realtime_api_events as ora

logger = logging.getLogger(__name__)

class DeviceConnection:
    def __init__(self, device: RemoteDevice):
        self.device = device
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.handler: Optional[UnmuteHandler] = None
        self.connected = False
        self.should_reconnect = True
        
    async def connect(self):
        """Connect to the remote device"""
        try:
            uri = f"ws://{self.device.host}:{self.device.port}/realtime"
            logger.info(f"Connecting to {self.device.name} at {uri}")
            
            self.websocket = await websockets.connect(
                uri,
                subprotocols=["realtime"]
            )
            
            self.handler = UnmuteHandler()
            await self.handler.start_up()
            
            # Send initial session configuration
            await self.configure_session()
            
            self.connected = True
            logger.info(f"Connected to {self.device.name}")
            
            # Start handling the connection
            await self.handle_connection()
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.device.name}: {e}")
            self.connected = False
            
            if self.device.auto_reconnect and self.should_reconnect:
                logger.info(f"Reconnecting to {self.device.name} in {self.device.reconnect_delay}s")
                await asyncio.sleep(self.device.reconnect_delay)
                await self.connect()
    
    async def configure_session(self):
        """Send session configuration to the device"""
        config = ora.SessionUpdate(
            session=ora.SessionConfig(
                instructions=self.device.instructions,
                voice=self.device.voice,
                allow_recording=False
            )
        )
        await self.websocket.send(config.model_dump_json())
    
    async def handle_connection(self):
        """Handle the WebSocket connection with the device"""
        try:
            # Create tasks for sending and receiving
            receive_task = asyncio.create_task(self.receive_loop())
            emit_task = asyncio.create_task(self.emit_loop())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [receive_task, emit_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                
        except ConnectionClosed:
            logger.info(f"Connection to {self.device.name} closed")
        except Exception as e:
            logger.error(f"Error handling connection to {self.device.name}: {e}")
        finally:
            self.connected = False
            if self.handler:
                await self.handler.cleanup()
    
    async def receive_loop(self):
        """Receive messages from the remote device"""
        async for message_raw in self.websocket:
            try:
                message = json.loads(message_raw)
                
                # Handle audio input from device
                if message["type"] == "input_audio_buffer.append":
                    # Process the same way as the original backend
                    opus_bytes = base64.b64decode(message["audio"])
                    pcm = await asyncio.to_thread(opus_reader.append_bytes, opus_bytes)
                    
                    if pcm.size and self.handler:
                        await self.handler.receive((SAMPLE_RATE, pcm[np.newaxis, :]))
                
                logger.debug(f"Received from {self.device.name}: {message['type']}")
                
            except Exception as e:
                logger.error(f"Error processing message from {self.device.name}: {e}")
    
    async def emit_loop(self):
        """Send messages to the remote device"""
        while self.connected and self.handler:
            try:
                # Get output from handler (same as original backend)
                emitted = await self.handler.emit()
                
                if emitted is None:
                    continue
                elif isinstance(emitted, ora.ServerEvent):
                    await self.websocket.send(emitted.model_dump_json())
                else:
                    # Handle audio output
                    _sr, audio = emitted
                    audio = audio_to_float32(audio)
                    opus_bytes = await asyncio.to_thread(opus_writer.append_pcm, audio)
                    
                    if opus_bytes:
                        response = ora.ResponseAudioDelta(
                            delta=base64.b64encode(opus_bytes).decode("utf-8")
                        )
                        await self.websocket.send(response.model_dump_json())
                        
            except Exception as e:
                logger.error(f"Error sending to {self.device.name}: {e}")
                break
    
    async def disconnect(self):
        """Disconnect from the device"""
        self.should_reconnect = False
        self.connected = False
        
        if self.websocket:
            await self.websocket.close()
        
        if self.handler:
            await self.handler.cleanup()

class DeviceManager:
    def __init__(self, config: RemoteDevicesConfig):
        self.config = config
        self.connections: Dict[str, DeviceConnection] = {}
        self.running = False
    
    async def start(self):
        """Start connecting to all configured devices"""
        self.running = True
        logger.info(f"Starting connections to {len(self.config.devices)} devices")
        
        # Create connection tasks for each device
        tasks = []
        for device in self.config.devices:
            connection = DeviceConnection(device)
            self.connections[device.name] = connection
            task = asyncio.create_task(connection.connect())
            tasks.append(task)
        
        # Wait for all connections (they will auto-reconnect)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop all device connections"""
        self.running = False
        logger.info("Stopping all device connections")
        
        disconnect_tasks = []
        for connection in self.connections.values():
            disconnect_tasks.append(connection.disconnect())
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        self.connections.clear()
    
    def get_connection_status(self) -> Dict[str, bool]:
        """Get connection status for all devices"""
        return {
            name: conn.connected 
            for name, conn in self.connections.items()
        }
```

#### 3. Modify Main Application

```python
# unmute/main_auto_connect.py
import asyncio
import logging
from fastapi import FastAPI
from unmute.device_manager import DeviceManager
from unmute.remote_devices import RemoteDevicesConfig, DEFAULT_DEVICES

app = FastAPI()
device_manager: DeviceManager = None

@app.on_event("startup")
async def startup_event():
    global device_manager
    
    # Load device configuration (from file, env vars, or defaults)
    config = RemoteDevicesConfig(devices=DEFAULT_DEVICES)
    
    device_manager = DeviceManager(config)
    
    # Start device connections in background
    asyncio.create_task(device_manager.start())
    
    logging.info("Auto-connection service started")

@app.on_event("shutdown") 
async def shutdown_event():
    global device_manager
    
    if device_manager:
        await device_manager.stop()
    
    logging.info("Auto-connection service stopped")

@app.get("/v1/devices/status")
async def get_device_status():
    """Get status of all device connections"""
    if device_manager:
        return device_manager.get_connection_status()
    return {}

@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "auto-connect"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Option 2: Remote Device WebSocket Server

Create a simple WebSocket server for your remote devices:

```python
# remote_device_server.py
import asyncio
import json
import base64
import logging
import websockets
from websockets.server import WebSocketServerProtocol
import pyaudio
import numpy as np
import sphn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RemoteDeviceServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.audio_stream = None
        self.opus_writer = sphn.OpusStreamWriter(24000)
        self.opus_reader = sphn.OpusStreamReader(24000)
        
        # Audio configuration
        self.sample_rate = 24000
        self.chunk_size = 1920  # 80ms at 24kHz
        self.channels = 1
        
    async def setup_audio(self):
        """Setup PyAudio for microphone input and speaker output"""
        self.audio = pyaudio.PyAudio()
        
        # Input stream (microphone)
        self.input_stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        # Output stream (speakers)
        self.output_stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=self.channels,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size
        )
        
        logger.info("Audio setup complete")
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket connection from backend"""
        logger.info(f"Backend connected from {websocket.remote_address}")
        
        try:
            # Start audio capture task
            audio_task = asyncio.create_task(self.audio_capture_loop(websocket))
            
            # Handle incoming messages
            async for message_raw in websocket:
                message = json.loads(message_raw)
                
                if message["type"] == "session.update":
                    logger.info(f"Session configured: {message['session']}")
                    
                elif message["type"] == "response.audio.delta":
                    # Play audio from backend
                    await self.play_audio(message["delta"])
                    
                elif message["type"] == "response.text.delta":
                    # Log text responses
                    print(f"Assistant: {message['delta']}", end="", flush=True)
                    
                else:
                    logger.debug(f"Received: {message['type']}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Backend disconnected")
        finally:
            audio_task.cancel()
    
    async def audio_capture_loop(self, websocket: WebSocketServerProtocol):
        """Continuously capture audio and send to backend"""
        while True:
            try:
                # Read audio from microphone
                audio_data = self.input_stream.read(self.chunk_size, exception_on_overflow=False)
                audio_np = np.frombuffer(audio_data, dtype=np.float32)
                
                # Encode to Opus
                opus_bytes = self.opus_writer.append_pcm(audio_np)
                
                if opus_bytes:
                    # Send to backend
                    message = {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(opus_bytes).decode('utf-8')
                    }
                    await websocket.send(json.dumps(message))
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.02)  # 20ms
                
            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                break
    
    async def play_audio(self, audio_base64: str):
        """Play audio received from backend"""
        try:
            opus_bytes = base64.b64decode(audio_base64)
            pcm_data = self.opus_reader.append_bytes(opus_bytes)
            
            if pcm_data.size > 0:
                # Write to output stream
                self.output_stream.write(pcm_data.astype(np.float32).tobytes())
                
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
    
    async def start_server(self):
        """Start the WebSocket server"""
        await self.setup_audio()
        
        logger.info(f"Starting server on {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            subprotocols=["realtime"]
        ):
            logger.info("Server started, waiting for connections...")
            await asyncio.Future()  # Run forever
    
    def cleanup(self):
        """Cleanup audio resources"""
        if hasattr(self, 'input_stream'):
            self.input_stream.stop_stream()
            self.input_stream.close()
        
        if hasattr(self, 'output_stream'):
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        if hasattr(self, 'audio'):
            self.audio.terminate()

async def main():
    server = RemoteDeviceServer(host="0.0.0.0", port=8765)
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration and Deployment

### 1. Environment Configuration

```bash
# .env file for backend
REMOTE_DEVICES_CONFIG=/path/to/devices.json
AUTO_CONNECT_ENABLED=true
```

### 2. Device Configuration File

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
      "reconnect_delay": 5.0
    },
    {
      "name": "kitchen",
      "host": "192.168.1.101",
      "port": 8765, 
      "voice": "Gertrude",
      "instructions": {"type": "constant", "text": "You are a helpful kitchen assistant"},
      "auto_reconnect": true,
      "reconnect_delay": 3.0
    }
  ]
}
```

### 3. Docker Compose Modification

```yaml
# docker-compose-autoconnect.yml
services:
  backend-autoconnect:
    build:
      context: ./
      dockerfile: Dockerfile
    command: ["python", "-m", "unmute.main_auto_connect"]
    environment:
      - KYUTAI_STT_URL=ws://stt:8080
      - KYUTAI_TTS_URL=ws://tts:8080  
      - KYUTAI_LLM_URL=http://llm:8000
      - REMOTE_DEVICES_CONFIG=/app/devices.json
    volumes:
      - ./devices.json:/app/devices.json
    ports:
      - "8000:8000"
    depends_on:
      - stt
      - tts
      - llm

  # ... other services (stt, tts, llm) remain the same
```

## Usage

### 1. Start Remote Device Server
```bash
# On each remote device
python remote_device_server.py
```

### 2. Start Backend with Auto-Connect
```bash
# On backend server
docker compose -f docker-compose-autoconnect.yml up
```

### 3. Monitor Connections
```bash
# Check device status
curl http://backend-ip:8000/v1/devices/status
```

## Benefits of This Approach

1. **No Frontend Required**: Eliminates the web interface completely
2. **Automatic Connection**: Backend initiates and maintains connections
3. **Auto-Reconnection**: Handles network interruptions gracefully  
4. **Multiple Devices**: Supports multiple simultaneous device connections
5. **Configuration-Driven**: Easy to add/remove devices via config files
6. **Monitoring**: Built-in status endpoints for connection monitoring

This setup creates a fully automated voice interaction system where the backend proactively connects to configured remote devices, eliminating any need for manual connection initiation.