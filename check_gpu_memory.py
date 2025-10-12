#!/usr/bin/env python3
"""
GPU Memory Usage Checker for Unmute Services

This script helps you monitor GPU memory usage and provides recommendations
for optimizing VRAM usage.
"""

import subprocess
import json
import re
import time
from datetime import datetime


def run_nvidia_smi():
    """Run nvidia-smi and parse the output."""
    try:
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return None, f"nvidia-smi failed: {result.stderr}"
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 6:
                    gpus.append({
                        'index': int(parts[0]),
                        'name': parts[1],
                        'memory_total': int(parts[2]),
                        'memory_used': int(parts[3]),
                        'memory_free': int(parts[4]),
                        'utilization': int(parts[5])
                    })
        
        return gpus, None
        
    except subprocess.TimeoutExpired:
        return None, "nvidia-smi timeout"
    except FileNotFoundError:
        return None, "nvidia-smi not found (NVIDIA drivers not installed?)"
    except Exception as e:
        return None, f"Error running nvidia-smi: {e}"


def get_docker_gpu_usage():
    """Get GPU usage by Docker containers."""
    try:
        # Get running containers
        result = subprocess.run([
            'docker', 'ps', '--format', 'json'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return [], f"Docker ps failed: {result.stderr}"
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    container = json.loads(line)
                    if any(keyword in container.get('Names', '').lower() 
                          for keyword in ['stt', 'tts', 'llm', 'unmute']):
                        containers.append(container)
                except json.JSONDecodeError:
                    continue
        
        return containers, None
        
    except Exception as e:
        return [], f"Error getting Docker containers: {e}"


def format_memory(mb):
    """Format memory in MB to human readable format."""
    if mb >= 1024:
        return f"{mb/1024:.1f} GB"
    else:
        return f"{mb} MB"


def print_gpu_status():
    """Print current GPU status."""
    print(f"\n🖥️  GPU Memory Status ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)
    
    gpus, error = run_nvidia_smi()
    if error:
        print(f"❌ {error}")
        return False
    
    if not gpus:
        print("❌ No GPUs found")
        return False
    
    total_used = 0
    total_available = 0
    
    for gpu in gpus:
        name = gpu['name']
        used = gpu['memory_used']
        total = gpu['memory_total']
        free = gpu['memory_free']
        util = gpu['utilization']
        
        usage_percent = (used / total) * 100 if total > 0 else 0
        
        # Color coding based on usage
        if usage_percent > 90:
            status_icon = "🔴"
        elif usage_percent > 70:
            status_icon = "🟡"
        else:
            status_icon = "🟢"
        
        print(f"{status_icon} GPU {gpu['index']}: {name}")
        print(f"   Memory: {format_memory(used)} / {format_memory(total)} ({usage_percent:.1f}%)")
        print(f"   Free: {format_memory(free)}")
        print(f"   Utilization: {util}%")
        print()
        
        total_used += used
        total_available += total
    
    print(f"📊 Total GPU Memory: {format_memory(total_used)} / {format_memory(total_available)}")
    
    return True


def print_docker_containers():
    """Print Docker containers using GPU."""
    print("\n🐳 Docker Containers (Unmute Services)")
    print("=" * 60)
    
    containers, error = get_docker_gpu_usage()
    if error:
        print(f"❌ {error}")
        return
    
    if not containers:
        print("ℹ️  No Unmute-related containers found")
        return
    
    for container in containers:
        name = container.get('Names', 'unknown')
        image = container.get('Image', 'unknown')
        status = container.get('State', 'unknown')
        
        status_icon = "🟢" if status == "running" else "🔴"
        
        print(f"{status_icon} {name}")
        print(f"   Image: {image}")
        print(f"   Status: {status}")
        print()


def print_memory_optimization_tips():
    """Print tips for reducing GPU memory usage."""
    print("\n💡 GPU Memory Optimization Tips")
    print("=" * 60)
    print()
    print("🔧 Quick Fixes:")
    print("   1. Use the low-memory Docker Compose:")
    print("      docker compose -f docker-compose.lowmem.yml up")
    print()
    print("   2. Reduce LLM model size:")
    print("      - Current: meta-llama/Llama-3.2-1B-Instruct (~2GB)")
    print("      - Smaller: microsoft/DialoGPT-small (~500MB)")
    print("      - Tiny: distilgpt2 (~300MB)")
    print()
    print("   3. Adjust GPU memory utilization:")
    print("      - LLM: --gpu-memory-utilization=0.2 (instead of 0.4)")
    print("      - Use CPU offloading: --cpu-offload-gb=2")
    print()
    print("   4. Reduce context length:")
    print("      - --max-model-len=512 (instead of 1536)")
    print()
    print("🏗️  Advanced Optimizations:")
    print("   1. Use model quantization (INT8/INT4)")
    print("   2. Enable gradient checkpointing")
    print("   3. Use separate GPUs for STT/TTS/LLM")
    print("   4. Implement model swapping/unloading")
    print()
    print("📋 Memory Requirements (Approximate):")
    print("   - STT Service: ~1-2 GB VRAM")
    print("   - TTS Service: ~2-3 GB VRAM") 
    print("   - LLM (1B model): ~2-3 GB VRAM")
    print("   - Total: ~5-8 GB VRAM minimum")
    print()


def monitor_memory_usage(interval=5, duration=60):
    """Monitor GPU memory usage over time."""
    print(f"\n📈 Monitoring GPU Memory (every {interval}s for {duration}s)")
    print("=" * 60)
    print("Press Ctrl+C to stop early")
    print()
    
    start_time = time.time()
    measurements = []
    
    try:
        while time.time() - start_time < duration:
            gpus, error = run_nvidia_smi()
            if not error and gpus:
                timestamp = datetime.now().strftime('%H:%M:%S')
                total_used = sum(gpu['memory_used'] for gpu in gpus)
                total_available = sum(gpu['memory_total'] for gpu in gpus)
                usage_percent = (total_used / total_available) * 100 if total_available > 0 else 0
                
                measurements.append({
                    'time': timestamp,
                    'used': total_used,
                    'total': total_available,
                    'percent': usage_percent
                })
                
                print(f"{timestamp}: {format_memory(total_used)} / {format_memory(total_available)} ({usage_percent:.1f}%)")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped")
    
    if measurements:
        print(f"\n📊 Summary ({len(measurements)} measurements):")
        avg_usage = sum(m['percent'] for m in measurements) / len(measurements)
        max_usage = max(m['percent'] for m in measurements)
        min_usage = min(m['percent'] for m in measurements)
        
        print(f"   Average: {avg_usage:.1f}%")
        print(f"   Maximum: {max_usage:.1f}%")
        print(f"   Minimum: {min_usage:.1f}%")


def main():
    """Main function."""
    print("🎮 Unmute GPU Memory Checker")
    print("=" * 60)
    
    # Check current status
    if not print_gpu_status():
        print("\n❌ Cannot access GPU information")
        print("   Make sure NVIDIA drivers and nvidia-smi are installed")
        return
    
    # Show Docker containers
    print_docker_containers()
    
    # Show optimization tips
    print_memory_optimization_tips()
    
    # Ask if user wants to monitor
    try:
        response = input("\n🔍 Monitor GPU usage over time? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            monitor_memory_usage()
    except KeyboardInterrupt:
        pass
    
    print("\n👋 Done!")


if __name__ == "__main__":
    main()