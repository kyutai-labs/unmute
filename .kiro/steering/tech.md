# Technology Stack

## Backend
- **Python 3.12**: Main backend language with strict type checking
- **FastAPI**: Web framework for REST API and WebSocket endpoints
- **WebSockets**: Real-time bidirectional communication using OpenAI Realtime API protocol
- **Pydantic**: Data validation and serialization
- **Prometheus**: Metrics collection and monitoring
- **Redis**: Caching layer
- **uv**: Python package manager and dependency management

## Frontend
- **Next.js 15**: React-based frontend framework
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first CSS framework
- **pnpm**: Package manager
- **WebSocket client**: Real-time communication with backend

## Audio Processing
- **Opus codec**: Audio compression for WebSocket transmission
- **sphn**: Audio stream processing library
- **fastrtc**: Real-time audio processing utilities
- **Kyutai STT/TTS models**: Optimized speech processing models

## LLM Integration
- **VLLM**: Default LLM serving (supports any OpenAI-compatible server)
- **OpenAI client**: Compatible API interface
- **Streaming responses**: Real-time text generation

## Infrastructure
- **Docker & Docker Compose**: Containerized deployment
- **Traefik**: Reverse proxy and load balancer
- **NVIDIA Container Toolkit**: GPU access for ML models
- **Docker Swarm**: Production scaling (optional)

## Development Tools
- **Ruff**: Python linting and formatting
- **Pyright**: Static type checking
- **ESLint**: JavaScript/TypeScript linting
- **pre-commit**: Git hooks for code quality
- **pytest**: Python testing framework

## Common Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Start backend (dev mode with hot reload)
uv run fastapi dev unmute/main_websocket.py

# Start frontend (dev mode)
cd frontend && pnpm install && pnpm dev

# Run all services with Docker Compose
docker compose up --build
```

### Dockerless Development
```bash
# Start individual services
./dockerless/start_backend.sh    # Backend on port 8000
./dockerless/start_frontend.sh   # Frontend on port 3000
./dockerless/start_llm.sh        # LLM server on port 8091
./dockerless/start_stt.sh        # STT service
./dockerless/start_tts.sh        # TTS service
```

### Code Quality
```bash
# Install pre-commit hooks
pre-commit install --hook-type pre-commit

# Run linting and formatting
uv run ruff check --fix
uv run ruff format
uv run pyright

# Frontend linting
cd frontend && pnpm run lint
```

### Testing
```bash
# Run Python tests
uv run pytest

# Run load testing
uv run unmute/loadtest/loadtest_client.py --server-url ws://localhost:8000 --n-workers 16
```

## Hardware Requirements
- **GPU**: CUDA-compatible with 16GB+ memory
- **OS**: Linux or Windows with WSL (Windows native not supported)
- **Memory**: Sufficient for concurrent STT, TTS, and LLM inference