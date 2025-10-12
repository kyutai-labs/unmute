# Project Structure

## Root Directory
- **pyproject.toml**: Python project configuration, dependencies, and tool settings
- **uv.lock**: Locked dependency versions for reproducible builds
- **docker-compose.yml**: Multi-service Docker setup for local development
- **swarm-deploy.yml**: Production Docker Swarm configuration
- **voices.yaml**: Character voice configurations and system prompts
- **Dockerfile**: Backend container definition

## Core Modules

### `/unmute/` - Main Backend Package
- **main_websocket.py**: FastAPI application entry point with WebSocket endpoints
- **unmute_handler.py**: Core handler orchestrating STT, LLM, and TTS services
- **openai_realtime_api_events.py**: OpenAI Realtime API protocol definitions
- **exceptions.py**: Custom exception classes for error handling
- **metrics.py**: Prometheus metrics collection
- **service_discovery.py**: Service health checking and discovery
- **kyutai_constants.py**: Configuration constants and environment variables

### `/unmute/llm/` - Language Model Integration
- LLM client implementations and streaming utilities
- System prompt generation and management
- Chatbot conversation handling

### `/unmute/stt/` - Speech-to-Text
- WebSocket client for STT service communication
- Audio stream processing and transcription handling

### `/unmute/tts/` - Text-to-Speech
- WebSocket client for TTS service communication
- Voice cloning and voice donation functionality
- Audio synthesis and streaming

### `/frontend/` - Next.js Web Application
- **src/**: React components and application logic
- **public/**: Static assets
- **package.json**: Node.js dependencies and scripts
- **next.config.ts**: Next.js configuration
- **tsconfig.json**: TypeScript configuration

## Services and Infrastructure

### `/services/` - External Service Configurations
- **moshi-server/**: STT and TTS service containers
- **grafana/**: Monitoring dashboard configuration
- **prometheus/**: Metrics collection configuration
- **debugger/**: Development debugging tools

### `/dockerless/` - Non-Docker Development Scripts
- Individual service startup scripts for local development
- Alternative to Docker Compose for development workflow

## Development and Documentation

### `/tests/` - Test Suite
- Python unit tests for backend functionality
- Test utilities and fixtures

### `/notebooks/` - Jupyter Notebooks
- Data analysis and experimentation notebooks
- Voice processing and model evaluation scripts

### `/docs/` - Documentation
- Technical documentation and API specifications
- Architecture diagrams and communication protocols

## Configuration Files
- **.pre-commit-config.yaml**: Git hooks for code quality enforcement
- **.gitignore**: Version control exclusions
- **LICENSE**: Project licensing information
- **README.md**: Project overview and setup instructions

## Architecture Patterns

### Service Communication
- **WebSocket-based**: Real-time bidirectional communication
- **Event-driven**: Message passing between services using defined protocols
- **Microservices**: Separate containers for STT, TTS, LLM, and backend coordination

### Code Organization
- **Modular design**: Clear separation between STT, TTS, LLM, and coordination logic
- **Type safety**: Strict typing with Pydantic models and TypeScript
- **Configuration-driven**: External YAML files for voice and character definitions
- **Async/await**: Non-blocking I/O throughout the application

### Error Handling
- **Graceful degradation**: Service availability checking and fallback behavior
- **Structured exceptions**: Custom exception hierarchy for different error types
- **Client communication**: Proper error reporting via WebSocket protocol