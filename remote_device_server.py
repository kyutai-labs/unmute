#!/usr/bin/env python3
"""
Simple WebSocket server for remote devices that the Unmute backend can connect to.

This script creates a WebSocket server that:
1. Accepts connections from the Unmute backend
2. Captures audio from the microphone
3. Sends audio to the backend via WebSocket
4. Receives and plays audio responses from the backend

Usage:
    python remote_device_server.py [--host HOST] [--port PORT] [--no-audio]
"""

import asyncio
import json
import base64
import logging
import argparse
import signal
import sys
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

# Optional audio dependencies
try:
    import pyaudio
    import numpy as np
    import sphn
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: Audio dependencies not available. Install with: pip install pyaudio numpy sphn")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockAudioProcessor:
    """Mock audio processor for when PyAudio is not available."""
    
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate
        self.chunk_size = 1920  # 80ms at 24kHz
        
    def setup_audio(self):
        logger.info("Mock audio setup (no real audio I/O)")
        
    def read_audio(self):
        # Return silence
        return np.zeros(self.chunk_size, dtype=np.float32)
        
    def write_audio(self, audio_data):
        # Do nothing
        pass
        
    def cleanup(self):
        pass


class AudioProcessor:
    """Real audio processor using PyAudio."""
    
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate
        self.chunk_size = 1920  # 80ms at 24kHz
        self.channels = 1
        
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        
        # Opus codecs
        self.opus_writer = sphn.OpusStreamWriter(sample_rate)
        self.opus_reader = sphn.OpusStreamReader(sample_rate)
        
    def setup_audio(self):
        """Setup PyAudio streams."""
        self.audio = pyaudio.PyAudio()
        
        # List available devices (for debugging)
        logger.info("Available audio devices:")
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            logger.info(f"  {i}: {info['name']} (in: {info['maxInputChannels']}, out: {info['maxOutputChannels']})")
        
        try:
            # Input stream (microphone)
            self.input_stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=None  # Use default device
            )
            
            # Output stream (speakers)
            self.output_stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size,
                output_device_index=None  # Use default device
            )
            
            logger.info("Audio streams initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize audio streams: {e}")
            raise
            
    def read_audio(self):
        """Read audio from microphone."""
        if not self.input_stream:
            return np.zeros(self.chunk_size, dtype=np.float32)
            
        try:
            audio_data = self.input_stream.read(
                self.chunk_size, 
                exception_on_overflow=False
            )
            return np.frombuffer(audio_data, dtype=np.float32)
        except Exception as e:
            logger.error(f"Error reading audio: {e}")
            return np.zeros(self.chunk_size, dtype=np.float32)
            
    def write_audio(self, audio_data):
        """Write audio to speakers."""
        if not self.output_stream:
            return
            
        try:
            self.output_stream.write(audio_data.astype(np.float32).tobytes())
        except Exception as e:
            logger.error(f"Error writing audio: {e}")
            
    def cleanup(self):
        """Cleanup audio resources."""
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            
        if self.audio:
            self.audio.terminate()


class RemoteDeviceServer:
    """WebSocket server for remote devices."""
    
    def __init__(self, host="0.0.0.0", port=8765, enable_audio=True):
        self.host = host
        self.port = port
        self.enable_audio = enable_audio and AUDIO_AVAILABLE
        
        # Audio processor
        if self.enable_audio:
            self.audio_processor = AudioProcessor()
        else:
            self.audio_processor = MockAudioProcessor()
            
        self.server = None
        self.connected_clients = set()
        self.running = False
        
    async def start_server(self):
        """Start the WebSocket server."""
        try:
            # Setup audio
            self.audio_processor.setup_audio()
            
            # Start WebSocket server
            logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
            
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                subprotocols=["realtime"],
                ping_interval=20,
                ping_timeout=10
            )
            
            self.running = True
            logger.info(f"Server started successfully. Waiting for connections...")
            
            # Keep server running
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
        finally:
            self.cleanup()
            
    async def stop_server(self):
        """Stop the WebSocket server."""
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        logger.info("Server stopped")
        
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket connection from backend."""
        client_addr = websocket.remote_address
        logger.info(f"Backend connected from {client_addr}")
        
        self.connected_clients.add(websocket)
        
        try:
            # Start audio capture task
            audio_task = asyncio.create_task(self.audio_capture_loop(websocket))
            
            # Handle incoming messages
            async for message_raw in websocket:
                try:
                    message = json.loads(message_raw)
                    await self.process_backend_message(websocket, message)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from backend: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Backend disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self.connected_clients.discard(websocket)
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass
                
    async def process_backend_message(self, websocket: WebSocketServerProtocol, message: dict):
        """Process message received from backend."""
        message_type = message.get("type")
        
        if message_type == "session.update":
            session = message.get("session", {})
            voice = session.get("voice", "unknown")
            instructions = session.get("instructions", {})
            logger.info(f"Session configured - Voice: {voice}, Instructions: {instructions}")
            
        elif message_type == "response.audio.delta":
            # Play audio from backend
            if self.enable_audio:
                await self.play_audio(message["delta"])
            else:
                logger.debug("Received audio (not playing - audio disabled)")
                
        elif message_type == "response.text.delta":
            # Log text responses
            text = message.get("delta", "")
            print(f"Assistant: {text}", end="", flush=True)
            
        elif message_type == "response.text.done":
            print()  # New line after complete response
            
        elif message_type == "conversation.item.input_audio_transcription.delta":
            # Log user transcription
            text = message.get("delta", "")
            print(f"User: {text}", end="", flush=True)
            
        else:
            logger.debug(f"Received: {message_type}")
            
    async def audio_capture_loop(self, websocket: WebSocketServerProtocol):
        """Continuously capture audio and send to backend."""
        logger.info("Starting audio capture loop")
        
        try:
            while self.running and not websocket.closed:
                try:
                    # Read audio from microphone
                    audio_np = self.audio_processor.read_audio()
                    
                    if self.enable_audio:
                        # Encode to Opus
                        opus_bytes = self.audio_processor.opus_writer.append_pcm(audio_np)
                        
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
                    
        except asyncio.CancelledError:
            logger.info("Audio capture loop cancelled")
        except Exception as e:
            logger.error(f"Audio capture loop error: {e}")
            
    async def play_audio(self, audio_base64: str):
        """Play audio received from backend."""
        try:
            opus_bytes = base64.b64decode(audio_base64)
            pcm_data = self.audio_processor.opus_reader.append_bytes(opus_bytes)
            
            if pcm_data.size > 0:
                self.audio_processor.write_audio(pcm_data)
                
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        self.audio_processor.cleanup()


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Remote Device WebSocket Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio processing")
    
    args = parser.parse_args()
    
    # Check audio availability
    if not AUDIO_AVAILABLE and not args.no_audio:
        logger.warning("Audio dependencies not available, running without audio")
        args.no_audio = True
    
    # Create server
    server = RemoteDeviceServer(
        host=args.host,
        port=args.port,
        enable_audio=not args.no_audio
    )
    
    # Setup signal handlers
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(server.stop_server())
    
    # Register signal handlers
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await server.stop_server()


if __name__ == "__main__":
    asyncio.run(main())