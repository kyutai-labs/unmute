"""Configuration for remote devices that the backend will connect to automatically."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class RemoteDevice(BaseModel):
    """Configuration for a single remote device."""
    name: str = Field(..., description="Unique name for the device")
    host: str = Field(..., description="IP address or hostname of the device")
    port: int = Field(default=8765, description="WebSocket port on the device")
    voice: str = Field(default="Watercooler", description="Voice to use for this device")
    instructions: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "smalltalk"},
        description="Instructions/system prompt for the device"
    )
    auto_reconnect: bool = Field(default=True, description="Whether to auto-reconnect on disconnect")
    reconnect_delay: float = Field(default=5.0, description="Delay in seconds before reconnecting")
    enabled: bool = Field(default=True, description="Whether this device is enabled")


class RemoteDevicesConfig(BaseModel):
    """Configuration for all remote devices."""
    devices: List[RemoteDevice] = Field(default_factory=list)
    
    @classmethod
    def load_from_file(cls, config_path: str | Path) -> "RemoteDevicesConfig":
        """Load configuration from a JSON file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    @classmethod
    def load_from_env(cls) -> "RemoteDevicesConfig":
        """Load configuration from environment variables or default file."""
        # Try environment variable first
        config_path = os.getenv("REMOTE_DEVICES_CONFIG")
        
        if config_path:
            return cls.load_from_file(config_path)
        
        # Try default locations
        default_paths = [
            Path("devices.json"),
            Path("/app/devices.json"),  # Docker container path
            Path("/config/devices.json"),
        ]
        
        for path in default_paths:
            if path.exists():
                return cls.load_from_file(path)
        
        # Return default configuration if no file found
        return cls(devices=DEFAULT_DEVICES)
    
    def get_enabled_devices(self) -> List[RemoteDevice]:
        """Get only enabled devices."""
        return [device for device in self.devices if device.enabled]


# Default configuration for testing/development
DEFAULT_DEVICES = [
    RemoteDevice(
        name="test_device",
        host="192.168.1.100",
        port=8765,
        voice="Watercooler",
        instructions={"type": "smalltalk"},
        auto_reconnect=True,
        reconnect_delay=5.0,
        enabled=False  # Disabled by default to avoid connection attempts
    )
]


def create_example_config(output_path: str | Path = "devices.json") -> None:
    """Create an example configuration file."""
    example_config = RemoteDevicesConfig(
        devices=[
            RemoteDevice(
                name="living_room",
                host="192.168.1.100",
                port=8765,
                voice="Watercooler",
                instructions={"type": "smalltalk"},
                auto_reconnect=True,
                reconnect_delay=5.0,
                enabled=True
            ),
            RemoteDevice(
                name="kitchen",
                host="192.168.1.101", 
                port=8765,
                voice="Gertrude",
                instructions={
                    "type": "constant",
                    "text": "You are a helpful kitchen assistant. Keep responses brief and practical."
                },
                auto_reconnect=True,
                reconnect_delay=3.0,
                enabled=True
            ),
            RemoteDevice(
                name="office",
                host="192.168.1.102",
                port=8765,
                voice="Dev (news)",
                instructions={
                    "type": "constant", 
                    "text": "You are a professional assistant for office work. Be concise and helpful."
                },
                auto_reconnect=True,
                reconnect_delay=5.0,
                enabled=False  # Disabled by default
            )
        ]
    )
    
    with open(output_path, 'w') as f:
        json.dump(example_config.model_dump(), f, indent=2)
    
    print(f"Example configuration created at: {output_path}")


if __name__ == "__main__":
    # Create example config when run directly
    create_example_config()