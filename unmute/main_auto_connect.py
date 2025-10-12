"""
Main application for auto-connecting backend that initiates connections to remote devices.

This replaces the original main_websocket.py for use cases where the backend should
connect to remote devices automatically rather than waiting for client connections.
"""

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from unmute.device_manager import DeviceManager
from unmute.remote_devices import RemoteDevicesConfig, create_example_config
from unmute import metrics as mt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global device manager
device_manager: Optional[DeviceManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global device_manager
    
    # Startup
    logger.info("Starting Unmute Auto-Connect Backend")
    
    try:
        # Load device configuration
        config = RemoteDevicesConfig.load_from_env()
        logger.info(f"Loaded configuration with {len(config.devices)} devices")
        
        # Log device configuration (without sensitive info)
        for device in config.devices:
            status = "enabled" if device.enabled else "disabled"
            logger.info(f"Device '{device.name}': {device.host}:{device.port} ({status})")
        
        # Create and start device manager
        device_manager = DeviceManager(config)
        await device_manager.start()
        
        logger.info("Auto-connect backend startup complete")
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.info("Creating example configuration file...")
        create_example_config("/app/devices.json")
        logger.info("Please edit /app/devices.json and restart the application")
        raise
        
    except Exception as e:
        logger.error(f"Failed to start auto-connect backend: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Unmute Auto-Connect Backend")
    
    if device_manager:
        await device_manager.stop()
    
    logger.info("Auto-connect backend shutdown complete")


# Create FastAPI app with lifespan management
app = FastAPI(
    title="Unmute Auto-Connect Backend",
    description="Backend that automatically connects to remote voice devices",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for development
CORS_ALLOW_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "service": "Unmute Auto-Connect Backend",
        "message": "Backend automatically connects to configured remote devices",
        "endpoints": {
            "health": "/v1/health",
            "devices": "/v1/devices",
            "status": "/v1/devices/status",
            "metrics": "/metrics"
        }
    }


@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    global device_manager
    
    if not device_manager:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": "Device manager not initialized"
            }
        )
    
    device_stats = device_manager.get_device_count()
    
    # Consider healthy if we have at least one connected device or no devices are configured
    is_healthy = (
        device_stats["connected"] > 0 or 
        device_stats["enabled"] == 0
    )
    
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "service": "auto-connect",
            "devices": device_stats,
            "message": f"{device_stats['connected']}/{device_stats['enabled']} devices connected"
        }
    )


@app.get("/v1/devices")
async def list_devices():
    """List all configured devices."""
    global device_manager
    
    if not device_manager:
        raise HTTPException(status_code=503, detail="Device manager not initialized")
    
    devices_info = []
    
    for device in device_manager.config.devices:
        devices_info.append({
            "name": device.name,
            "host": device.host,
            "port": device.port,
            "voice": device.voice,
            "enabled": device.enabled,
            "auto_reconnect": device.auto_reconnect,
            "reconnect_delay": device.reconnect_delay
        })
    
    return {
        "devices": devices_info,
        "total_count": len(devices_info)
    }


@app.get("/v1/devices/status")
async def get_device_status():
    """Get detailed connection status for all devices."""
    global device_manager
    
    if not device_manager:
        raise HTTPException(status_code=503, detail="Device manager not initialized")
    
    status = device_manager.get_connection_status()
    stats = device_manager.get_device_count()
    
    return {
        "devices": status,
        "summary": stats,
        "timestamp": asyncio.get_event_loop().time()
    }


@app.post("/v1/devices/{device_name}/reconnect")
async def reconnect_device(device_name: str):
    """Manually trigger reconnection for a specific device."""
    global device_manager
    
    if not device_manager:
        raise HTTPException(status_code=503, detail="Device manager not initialized")
    
    if device_name not in device_manager.connections:
        raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found")
    
    connection = device_manager.connections[device_name]
    
    # Stop and restart the connection
    await connection.stop()
    await connection.start()
    
    return {
        "message": f"Reconnection initiated for device '{device_name}'",
        "device": device_name
    }


@app.get("/v1/config/example")
async def get_example_config():
    """Get an example configuration file."""
    from unmute.remote_devices import DEFAULT_DEVICES
    
    example_config = RemoteDevicesConfig(devices=DEFAULT_DEVICES)
    
    return {
        "example_config": example_config.model_dump(),
        "description": "Example configuration for devices.json",
        "note": "Set 'enabled': true and update host/port for your devices"
    }


# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    # FastAPI will handle the shutdown via lifespan context manager


if __name__ == "__main__":
    import uvicorn
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")
    
    logger.info(f"Starting server on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        "unmute.main_auto_connect:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False  # Disable reload for production
    )