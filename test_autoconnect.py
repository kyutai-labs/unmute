#!/usr/bin/env python3
"""
Test script for the auto-connect backend setup.

This script helps verify that the auto-connect backend is working correctly.
"""

import asyncio
import json
import requests
import sys
from pathlib import Path


def test_config_file():
    """Test if configuration file exists and is valid."""
    print("🔍 Testing configuration file...")
    
    config_path = Path("devices.json")
    if not config_path.exists():
        print("❌ devices.json not found")
        print("   Run: cp devices.example.json devices.json")
        return False
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        devices = config.get("devices", [])
        print(f"✅ Configuration loaded: {len(devices)} devices configured")
        
        enabled_count = sum(1 for d in devices if d.get("enabled", False))
        print(f"   {enabled_count} devices enabled")
        
        if enabled_count == 0:
            print("⚠️  No devices are enabled. Set 'enabled': true in devices.json")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in devices.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading devices.json: {e}")
        return False


def test_backend_health(url="http://localhost:8000"):
    """Test if the backend is running and healthy."""
    print(f"🔍 Testing backend health at {url}...")
    
    try:
        response = requests.get(f"{url}/v1/health", timeout=5)
        
        if response.status_code == 200:
            health = response.json()
            print("✅ Backend is healthy")
            print(f"   Status: {health.get('status')}")
            print(f"   Devices: {health.get('devices', {})}")
            return True
        else:
            print(f"❌ Backend unhealthy: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend")
        print("   Is the backend running? Try: docker compose -f docker-compose.autoconnect.yml up")
        return False
    except Exception as e:
        print(f"❌ Error checking backend health: {e}")
        return False


def test_device_status(url="http://localhost:8000"):
    """Test device connection status."""
    print(f"🔍 Testing device connections at {url}...")
    
    try:
        response = requests.get(f"{url}/v1/devices/status", timeout=5)
        
        if response.status_code == 200:
            status = response.json()
            devices = status.get("devices", {})
            summary = status.get("summary", {})
            
            print("✅ Device status retrieved")
            print(f"   Total: {summary.get('total', 0)}")
            print(f"   Enabled: {summary.get('enabled', 0)}")
            print(f"   Connected: {summary.get('connected', 0)}")
            
            for name, info in devices.items():
                connected = "🟢" if info.get("connected") else "🔴"
                print(f"   {connected} {name}: {info.get('device_host')}:{info.get('device_port')}")
            
            return summary.get("connected", 0) > 0
            
        else:
            print(f"❌ Cannot get device status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking device status: {e}")
        return False


def test_remote_device_connectivity():
    """Test if remote devices are reachable."""
    print("🔍 Testing remote device connectivity...")
    
    config_path = Path("devices.json")
    if not config_path.exists():
        print("⚠️  No devices.json found, skipping connectivity test")
        return True
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        devices = config.get("devices", [])
        enabled_devices = [d for d in devices if d.get("enabled", False)]
        
        if not enabled_devices:
            print("⚠️  No enabled devices to test")
            return True
        
        import socket
        
        reachable_count = 0
        for device in enabled_devices:
            name = device.get("name", "unknown")
            host = device.get("host")
            port = device.get("port", 8765)
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    print(f"   ✅ {name} ({host}:{port}) - reachable")
                    reachable_count += 1
                else:
                    print(f"   ❌ {name} ({host}:{port}) - not reachable")
                    
            except Exception as e:
                print(f"   ❌ {name} ({host}:{port}) - error: {e}")
        
        print(f"   {reachable_count}/{len(enabled_devices)} devices reachable")
        return reachable_count > 0
        
    except Exception as e:
        print(f"❌ Error testing device connectivity: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Testing Unmute Auto-Connect Setup")
    print("=" * 50)
    
    tests = [
        ("Configuration File", test_config_file),
        ("Backend Health", test_backend_health),
        ("Device Status", test_device_status),
        ("Device Connectivity", test_remote_device_connectivity),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Your auto-connect setup looks good.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        
        print("\n💡 Common solutions:")
        print("   - Ensure devices.json exists and has enabled devices")
        print("   - Start the backend: docker compose -f docker-compose.autoconnect.yml up")
        print("   - Start remote device servers: python remote_device_server.py")
        print("   - Check network connectivity between backend and devices")
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)