"""Device connection manager for auto-connecting to remote devices."""

import asyncio
import base64
import json
import logging
from typing import Dict, Optional
import numpy as np
import sphn
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

from unmute.unmute_handler import UnmuteHandler
from unmute.remote_devices import RemoteDevice, RemoteDevicesConfig
import unmute.openai_realtime_api_events as ora
from unmute.kyutai_constants import SAMPLE_RATE
from fastrtc import audio_to_float32

logger = logging.getLogger(__name__)


class DeviceConnection:
    """Manages a single connection to a remote device."""
    
    def __init__(self, device: RemoteDevice):
        self.device = device
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.handler: Optional[UnmuteHandler] = None
        self.connected = False
        self.should_reconnect = True
        self.connection_task: Optional[asyncio.Task] = None
        
        # Audio processing
        self.opus_reader = sphn.OpusStreamReader(SAMPLE_RATE)
        self.opus_writer = sphn.OpusStreamWriter(SAMPLE_RATE)
        
    async def start(self):
        """Start the connection (with auto-reconnect)."""
        self.should_reconnect = True
        self.connection_task = asyncio.create_task(self._connection_loop())
        
    async def stop(self):
        """Stop the connection and disable reconnection."""
        self.should_reconnect = False
        self.connected = False
        
        if self.connection_task:
            self.connection_task.cancel()
            try:
                await self.connection_task
            except asyncio.CancelledError:
                pass
        
        await self._cleanup()
        
    async def _connection_loop(self):
        """Main connection loop with auto-reconnect."""
        while self.should_reconnect:
            try:
                await self._connect_and_handle()
            except Exception as e:
                logger.error(f"Connection error for {self.device.name}: {e}")
                
            if self.should_reconnect and self.device.auto_reconnect:
                logger.info(f"Reconnecting to {self.device.name} in {self.device.reconnect_delay}s")
                await asyncio.sleep(self.device.reconnect_delay)
            else:
                break
                
        await self._cleanup()
        
    async def _connect_and_handle(self):
        """Connect to device and handle the connection."""
        uri = f"ws://{self.device.host}:{self.device.port}/realtime"
        logger.info(f"Connecting to {self.device.name} at {uri}")
        
        try:
            # Connect with timeout
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    uri,
                    subprotocols=["realtime"],
                    ping_interval=20,  # Keep connection alive
                    ping_timeout=10,
                    close_timeout=10
                ),
                timeout=10.0
            )
            
            # Initialize handler
            self.handler = UnmuteHandler()
            async with self.handler:
                await self.handler.start_up()
                
                # Send initial session configuration
                await self._configure_session()
                
                self.connected = True
                logger.info(f"Connected to {self.device.name}")
                
                # Handle the connection
                await self._handle_connection()
                
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout for {self.device.name}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to {self.device.name}: {e}")
            raise
        finally:
            self.connected = False
            
    async def _configure_session(self):
        """Send session configuration to the device."""
        config = ora.SessionUpdate(
            session=ora.SessionConfig(
                instructions=self.device.instructions,
                voice=self.device.voice,
                allow_recording=False
            )
        )
        await self.websocket.send(config.model_dump_json())
        logger.debug(f"Session configured for {self.device.name}")
        
    async def _handle_connection(self):
        """Handle the WebSocket connection with the device."""
        try:
            # Create tasks for sending and receiving
            receive_task = asyncio.create_task(self._receive_loop())
            emit_task = asyncio.create_task(self._emit_loop())
            
            # Wait for either task to complete or fail
            done, pending = await asyncio.wait(
                [receive_task, emit_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except ConnectionClosed:
            logger.info(f"Connection to {self.device.name} closed")
        except Exception as e:
            logger.error(f"Error handling connection to {self.device.name}: {e}")
            raise
            
    async def _receive_loop(self):
        """Receive messages from the remote device."""
        try:
            async for message_raw in self.websocket:
                try:
                    message = json.loads(message_raw)
                    await self._process_device_message(message)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {self.device.name}: {e}")
                except Exception as e:
                    logger.error(f"Error processing message from {self.device.name}: {e}")
                    
        except ConnectionClosed:
            logger.info(f"Receive loop ended for {self.device.name}")
            raise
        except Exception as e:
            logger.error(f"Receive loop error for {self.device.name}: {e}")
            raise
            
    async def _process_device_message(self, message: dict):
        """Process a message received from the device."""
        message_type = message.get("type")
        
        if message_type == "input_audio_buffer.append":
            # Handle audio input from device
            try:
                opus_bytes = base64.b64decode(message["audio"])
                pcm = await asyncio.to_thread(self.opus_reader.append_bytes, opus_bytes)
                
                if pcm.size > 0 and self.handler:
                    await self.handler.receive((SAMPLE_RATE, pcm[np.newaxis, :]))
                    
            except Exception as e:
                logger.error(f"Error processing audio from {self.device.name}: {e}")
                
        elif message_type == "session.update":
            # Device is updating session config
            logger.debug(f"Session update from {self.device.name}: {message}")
            
        else:
            logger.debug(f"Received from {self.device.name}: {message_type}")
            
    async def _emit_loop(self):
        """Send messages to the remote device."""
        try:
            while self.connected and self.handler and self.websocket:
                try:
                    # Get output from handler
                    emitted = await self.handler.emit()
                    
                    if emitted is None:
                        continue
                        
                    await self._send_to_device(emitted)
                    
                except Exception as e:
                    logger.error(f"Error in emit loop for {self.device.name}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Emit loop error for {self.device.name}: {e}")
            raise
            
    async def _send_to_device(self, emitted):
        """Send emitted data to the device."""
        try:
            if isinstance(emitted, ora.ServerEvent):
                # Send server event as JSON
                await self.websocket.send(emitted.model_dump_json())
                
            else:
                # Handle audio output
                _sr, audio = emitted
                audio = audio_to_float32(audio)
                opus_bytes = await asyncio.to_thread(self.opus_writer.append_pcm, audio)
                
                if opus_bytes:
                    response = ora.ResponseAudioDelta(
                        delta=base64.b64encode(opus_bytes).decode("utf-8")
                    )
                    await self.websocket.send(response.model_dump_json())
                    
        except Exception as e:
            logger.error(f"Error sending to {self.device.name}: {e}")
            raise
            
    async def _cleanup(self):
        """Clean up connection resources."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
            
        if self.handler:
            try:
                await self.handler.cleanup()
            except Exception:
                pass
            self.handler = None


class DeviceManager:
    """Manages connections to multiple remote devices."""
    
    def __init__(self, config: RemoteDevicesConfig):
        self.config = config
        self.connections: Dict[str, DeviceConnection] = {}
        self.running = False
        
    async def start(self):
        """Start connecting to all enabled devices."""
        if self.running:
            logger.warning("DeviceManager already running")
            return
            
        self.running = True
        enabled_devices = self.config.get_enabled_devices()
        
        if not enabled_devices:
            logger.warning("No enabled devices found in configuration")
            return
            
        logger.info(f"Starting connections to {len(enabled_devices)} devices")
        
        # Start connections for each enabled device
        for device in enabled_devices:
            try:
                connection = DeviceConnection(device)
                self.connections[device.name] = connection
                await connection.start()
                logger.info(f"Started connection manager for {device.name}")
                
            except Exception as e:
                logger.error(f"Failed to start connection for {device.name}: {e}")
                
        logger.info("All device connection managers started")
        
    async def stop(self):
        """Stop all device connections."""
        if not self.running:
            return
            
        self.running = False
        logger.info("Stopping all device connections")
        
        # Stop all connections
        stop_tasks = []
        for connection in self.connections.values():
            stop_tasks.append(connection.stop())
            
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
            
        self.connections.clear()
        logger.info("All device connections stopped")
        
    def get_connection_status(self) -> Dict[str, dict]:
        """Get detailed status of all device connections."""
        status = {}
        
        for name, connection in self.connections.items():
            status[name] = {
                "connected": connection.connected,
                "device_host": connection.device.host,
                "device_port": connection.device.port,
                "voice": connection.device.voice,
                "auto_reconnect": connection.device.auto_reconnect,
                "enabled": connection.device.enabled
            }
            
        return status
        
    def get_device_count(self) -> dict:
        """Get count statistics."""
        total_devices = len(self.config.devices)
        enabled_devices = len(self.config.get_enabled_devices())
        connected_devices = sum(1 for conn in self.connections.values() if conn.connected)
        
        return {
            "total": total_devices,
            "enabled": enabled_devices,
            "connected": connected_devices
        }