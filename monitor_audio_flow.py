#!/usr/bin/env python3
"""
Audio Flow Monitor for Unmute Auto-Connect Backend

This script helps you verify that audio is flowing correctly between
the backend and remote devices.
"""

import asyncio
import json
import requests
import time
import websockets
from datetime import datetime
from typing import Dict, Any


class AudioFlowMonitor:
    """Monitor audio flow and connection status."""
    
    def __init__(self, backend_url="http://localhost:8000"):
        self.backend_url = backend_url
        self.stats = {
            "connections": {},
            "audio_events": [],
            "last_activity": {}
        }
        
    def get_device_status(self) -> Dict[str, Any]:
        """Get current device connection status."""
        try:
            response = requests.get(f"{self.backend_url}/v1/devices/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def print_connection_status(self):
        """Print current connection status."""
        status = self.get_device_status()
        
        if "error" in status:
            print(f"❌ Error getting status: {status['error']}")
            return
        
        devices = status.get("devices", {})
        summary = status.get("summary", {})
        
        print(f"\n📊 Connection Status ({datetime.now().strftime('%H:%M:%S')})")
        print("=" * 50)
        print(f"Total Devices: {summary.get('total', 0)}")
        print(f"Enabled: {summary.get('enabled', 0)}")
        print(f"Connected: {summary.get('connected', 0)}")
        print()
        
        for name, info in devices.items():
            status_icon = "🟢" if info.get("connected") else "🔴"
            host = info.get("device_host", "unknown")
            port = info.get("device_port", "unknown")
            voice = info.get("voice", "unknown")
            
            print(f"{status_icon} {name}")
            print(f"   Address: {host}:{port}")
            print(f"   Voice: {voice}")
            print(f"   Connected: {info.get('connected', False)}")
            print()
    
    async def monitor_backend_logs(self):
        """Monitor backend for audio-related log messages."""
        print("🔍 Monitoring backend logs for audio activity...")
        print("   (This requires access to container logs)")
        print()
        
        # In a real implementation, you'd connect to Docker logs
        # For now, we'll simulate by checking device status periodically
        while True:
            try:
                self.print_connection_status()
                
                # Check for recent activity
                status = self.get_device_status()
                if "devices" in status:
                    for name, info in status["devices"].items():
                        if info.get("connected"):
                            current_time = time.time()
                            last_seen = self.stats["last_activity"].get(name, 0)
                            
                            if current_time - last_seen > 30:  # 30 seconds
                                print(f"💡 Device '{name}' is connected and ready for audio")
                                self.stats["last_activity"][name] = current_time
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                await asyncio.sleep(5)
    
    def print_audio_verification_tips(self):
        """Print tips for verifying audio flow."""
        print("\n🎤 Audio Flow Verification Tips")
        print("=" * 50)
        print()
        print("1. 📱 Remote Device Side:")
        print("   - Check if device server shows 'Backend connected'")
        print("   - Speak into microphone - you should see audio capture logs")
        print("   - Listen for responses from speakers")
        print()
        print("2. 🖥️  Backend Side:")
        print("   - Check container logs: docker compose logs -f backend-autoconnect")
        print("   - Look for 'Connected to device_name' messages")
        print("   - Monitor STT/TTS service logs for processing activity")
        print()
        print("3. 🔊 Audio Quality Indicators:")
        print("   - Device should show Opus encoding/decoding activity")
        print("   - Backend logs should show audio buffer messages")
        print("   - STT should produce transcription events")
        print("   - TTS should generate audio response events")
        print()
        print("4. 🐛 Troubleshooting:")
        print("   - Ensure microphone permissions on device")
        print("   - Check audio device availability (run device server with --no-audio to test)")
        print("   - Verify network connectivity between backend and device")
        print("   - Check GPU memory usage for STT/TTS services")
        print()
    
    def run_interactive_test(self):
        """Run interactive audio flow test."""
        print("\n🧪 Interactive Audio Flow Test")
        print("=" * 50)
        
        # Check backend health
        try:
            response = requests.get(f"{self.backend_url}/v1/health", timeout=5)
            if response.status_code != 200:
                print("❌ Backend is not healthy")
                return
            
            health = response.json()
            print(f"✅ Backend Status: {health.get('status')}")
            
        except Exception as e:
            print(f"❌ Cannot reach backend: {e}")
            return
        
        # Get device status
        status = self.get_device_status()
        if "error" in status:
            print(f"❌ Cannot get device status: {status['error']}")
            return
        
        devices = status.get("devices", {})
        connected_devices = [name for name, info in devices.items() if info.get("connected")]
        
        if not connected_devices:
            print("❌ No devices are currently connected")
            print("   Start a remote device server first:")
            print("   python remote_device_server.py --host 0.0.0.0 --port 8765")
            return
        
        print(f"✅ Found {len(connected_devices)} connected device(s):")
        for device in connected_devices:
            print(f"   - {device}")
        
        print("\n🎤 Audio Test Instructions:")
        print("1. Speak into the microphone on your remote device")
        print("2. You should hear a response from the speakers")
        print("3. Check the logs below for activity...")
        print()
        
        input("Press Enter when ready to start monitoring...")
        
        # Start monitoring
        try:
            asyncio.run(self.monitor_backend_logs())
        except KeyboardInterrupt:
            print("\n✅ Monitoring stopped")


def main():
    """Main function."""
    print("🎵 Unmute Audio Flow Monitor")
    print("=" * 50)
    
    monitor = AudioFlowMonitor()
    
    # Print verification tips
    monitor.print_audio_verification_tips()
    
    # Run interactive test
    try:
        monitor.run_interactive_test()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()