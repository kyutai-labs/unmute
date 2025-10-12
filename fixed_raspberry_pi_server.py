#!/usr/bin/env python3
"""
Fixed Audio WebSocket Server for Raspberry Pi
Compatible with Unmute Auto-Connect Backend Protocol

This server implements the OpenAI Realtime API protocol that the backend expects.
"""

import asyncio
import websockets
import pyaudio
import json
import logging
import base64
import numpy as np
from datetime import datetime
from typing import Optional, Set
from websockets.server import WebSocketServerProtocol

# Try to import sphn for Opus encoding, fallback to PCM if not available
try:
    import sphn
    OPUS_AVAILABLE = True
    print("✅ Opus encoding available")
except ImportError:
    OPUS_AVAILABLE = False
    print("⚠️  Opus not available, using PCM (install sphn for better performance)")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Audio configuration - matching backend expectations
AUDIO_FORMAT = pyaudio.paFloat32  # Float32 for better compatibility
CHANNELS = 1  # Mono
RATE = 24000  # 24kHz to match backend
CHUNK = 1920  # 80ms at 24kHz (1920 samples = 80ms)

# Device names (adjust for your hardware)
INPUT_DEVICE_NAME = "USB PnP Sound Device"
OUTPUT_DEVICE_NAME = "MAX98357A"


class UnmuteCompatibleServer:
    """WebSocket server compatible with Unmute backend protocol."""
    
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.audio = pyaudio.PyAudio()
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.input_device_index: Optional[int] = None
        self.output_device_index: Optional[int] = None
        
        # Audio processing
        if OPUS_AVAILABLE:
            self.opus_writer = sphn.OpusStreamWriter(RATE)
            self.opus_reader = sphn.OpusStreamReader(RATE)
        else:
            self.opus_writer = None
            self.opus_reader = None
        
        # Audio streams
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None
        
        # Find audio devices
        self._find_audio_devices()
        
    def _find_audio_devices(self):
        """Find input and output device indices."""
        logger.info("Scanning audio devices...")
        
        for i in range(self.audio.get_device_count()):
            try:
                device_info = self.audio.get_device_info_by_index(i)
                device_name = device_info.get('name', '')
                
                logger.debug(f"Device {i}: {device_name} "
                           f"(in: {device_info.get('maxInputChannels', 0)}, "
                           f"out: {device_info.get('maxOutputChannels', 0)})")
                
                # Find input device
                if (INPUT_DEVICE_NAME in device_name and 
                    device_info.get('maxInputChannels', 0) > 0):
                    self.input_device_index = i
                    logger.info(f"✅ Found input device: {device_name} (index: {i})")
                
                # Find output device  
                if (OUTPUT_DEVICE_NAME in device_name and 
                    device_info.get('maxOutputChannels', 0) > 0):
                    self.output_device_index = i
                    logger.info(f"✅ Found output device: {device_name} (index: {i})")
                    
            except Exception as e:
                logger.debug(f"Error checking device {i}: {e}")
        
        if self.input_device_index is None:
            logger.warning(f"⚠️  Input device '{INPUT_DEVICE_NAME}' not found. Using default.")
            
        if self.output_device_index is None:
            logger.warning(f"⚠️  Output device '{OUTPUT_DEVICE_NAME}' not found. Using default.")
    
    def _setup_audio_streams(self):
        """Setup audio input and output streams."""
        try:
            # Input stream (microphone)
            self.input_stream = self.audio.open(
                format=AUDIO_FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=CHUNK,
                stream_callback=None  # We'll read manually
            )
            logger.info("✅ Audio input stream opened")
            
            # Output stream (speakers)
            self.output_stream = self.audio.open(
                format=AUDIO_FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                output_device_index=self.output_device_index,
                frames_per_buffer=CHUNK
            )
            logger.info("✅ Audio output stream opened")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup audio streams: {e}")
            raise
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket connection from Unmute backend."""
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔗 Backend connected: {client_addr}")
        
        # Add to connected clients
        self.connected_clients.add(websocket)
        
        try:
            # Handle incoming messages from backend
            async for message_raw in websocket:
                try:
                    if isinstance(message_raw, str):
                        message = json.loads(message_raw)
                        await self._process_backend_message(websocket, message)
                    else:
                        logger.warning(f"Received non-text message: {type(message_raw)}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON from backend: {e}")
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Backend disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"❌ Connection error with {client_addr}: {e}")
        finally:
            # Remove from connected clients
            self.connected_clients.discard(websocket)
            logger.info(f"🧹 Cleaned up connection: {client_addr}")
    
    async def _process_backend_message(self, websocket: WebSocketServerProtocol, message: dict):
        """Process message received from backend."""
        message_type = message.get("type")
        
        if message_type == "session.update":
            # Backend is configuring the session
            session = message.get("session", {})
            voice = session.get("voice", "unknown")
            instructions = session.get("instructions", {})
            logger.info(f"📋 Session configured - Voice: {voice}")
            logger.debug(f"Instructions: {instructions}")
            
        elif message_type == "response.audio.delta":
            # Backend is sending audio to play
            await self._play_audio_from_backend(message.get("delta", ""))
            
        elif message_type == "response.text.delta":
            # Backend is sending text response
            text = message.get("delta", "")
            print(f"🤖 Assistant: {text}", end="", flush=True)
            
        elif message_type == "response.text.done":
            # Complete text response received
            print()  # New line
            
        elif message_type == "conversation.item.input_audio_transcription.delta":
            # Backend is sending transcription of our audio
            text = message.get("delta", "")
            print(f"🎤 User: {text}", end="", flush=True)
            
        elif message_type in [
            "response.created", "response.audio.done", 
            "input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"
        ]:
            # Expected messages that we can ignore
            logger.debug(f"📨 Received: {message_type}")
            
        else:
            logger.debug(f"❓ Unknown message type: {message_type}")
    
    async def _play_audio_from_backend(self, audio_base64: str):
        """Play audio received from backend."""
        if not audio_base64 or not self.output_stream:
            return
            
        try:
            if OPUS_AVAILABLE and self.opus_reader:
                # Decode Opus audio
                opus_bytes = base64.b64decode(audio_base64)
                pcm_data = await asyncio.to_thread(self.opus_reader.append_bytes, opus_bytes)
                
                if pcm_data.size > 0:
                    # Convert to the format expected by PyAudio
                    audio_data = pcm_data.astype(np.float32)
                    self.output_stream.write(audio_data.tobytes())
            else:
                # Fallback: assume it's base64-encoded PCM
                audio_bytes = base64.b64decode(audio_base64)
                self.output_stream.write(audio_bytes)
                
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
    
    async def _audio_capture_loop(self):
        """Continuously capture audio and send to backend."""
        logger.info("🎤 Starting audio capture loop...")
        
        if not self.input_stream:
            logger.error("❌ No input stream available")
            return
        
        try:
            while True:
                if not self.connected_clients:
                    # No clients connected, just wait
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    # Read audio from microphone
                    audio_data = await asyncio.to_thread(
                        self.input_stream.read, 
                        CHUNK, 
                        exception_on_overflow=False
                    )
                    
                    # Convert to numpy array
                    audio_np = np.frombuffer(audio_data, dtype=np.float32)
                    
                    # Encode audio for transmission
                    if OPUS_AVAILABLE and self.opus_writer:
                        # Use Opus encoding (preferred)
                        opus_bytes = await asyncio.to_thread(
                            self.opus_writer.append_pcm, 
                            audio_np
                        )
                        
                        if opus_bytes:
                            # Send as OpenAI Realtime API message
                            message = {
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(opus_bytes).decode('utf-8')
                            }
                            await self._send_to_all_clients(json.dumps(message))
                    else:
                        # Fallback: send as base64-encoded PCM
                        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                        message = {
                            "type": "input_audio_buffer.append", 
                            "audio": audio_b64
                        }
                        await self._send_to_all_clients(json.dumps(message))
                    
                    # Small delay to prevent CPU overload
                    await asyncio.sleep(0.01)  # 10ms
                    
                except Exception as e:
                    logger.error(f"❌ Audio capture error: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"❌ Audio capture loop error: {e}")
    
    async def _send_to_all_clients(self, message: str):
        """Send message to all connected clients."""
        if not self.connected_clients:
            return
        
        # Create a copy of the set to avoid "set changed size during iteration"
        clients_copy = self.connected_clients.copy()
        disconnected_clients = set()
        
        for client in clients_copy:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ Error sending to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected_clients
        
        if disconnected_clients:
            logger.debug(f"🧹 Removed {len(disconnected_clients)} disconnected clients")
    
    async def start_server(self):
        """Start the WebSocket server and audio processing."""
        logger.info(f"🚀 Starting Unmute-compatible server on {self.host}:{self.port}")
        
        # Setup audio streams
        self._setup_audio_streams()
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            subprotocols=["realtime"],  # Required by backend
            ping_interval=30,  # Longer ping interval
            ping_timeout=15,   # Longer timeout
            close_timeout=10
        )
        
        # Start audio capture task
        capture_task = asyncio.create_task(self._audio_capture_loop())
        
        logger.info("✅ Server started successfully!")
        logger.info(f"🎯 Waiting for Unmute backend connections on ws://{self.host}:{self.port}/realtime")
        logger.info("Press Ctrl+C to stop")
        
        try:
            # Keep server running
            await asyncio.gather(
                server.wait_closed(),
                capture_task
            )
        except asyncio.CancelledError:
            logger.info("🛑 Server shutdown requested")
            capture_task.cancel()
            server.close()
            await server.wait_closed()
    
    def cleanup(self):
        """Clean up audio resources."""
        logger.info("🧹 Cleaning up audio resources...")
        
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            
        self.audio.terminate()
        logger.info("✅ Audio cleanup complete")


async def main():
    """Main function."""
    # Check dependencies
    if not OPUS_AVAILABLE:
        logger.warning("⚠️  Opus encoding not available. Install with: pip install sphn")
        logger.warning("   Audio will use PCM encoding (less efficient)")
    
    server = UnmuteCompatibleServer(host='0.0.0.0', port=8765)
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down server...")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
    finally:
        server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())