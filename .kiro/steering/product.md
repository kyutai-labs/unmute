# Product Overview

Unmute is a real-time voice conversation system that enables text-based LLMs to listen and speak. It wraps any text LLM with Kyutai's optimized Speech-to-Text (STT) and Text-to-Speech (TTS) models to create a seamless voice interaction experience.

## Core Functionality

- **Real-time voice conversations**: Users speak to the system, which transcribes their speech, generates LLM responses, and reads them back aloud
- **Low-latency audio processing**: Optimized for minimal delay between user input and system response
- **Multiple character voices**: Configurable personas with different voices and conversation styles
- **WebSocket-based communication**: Real-time bidirectional communication between browser and backend
- **LLM agnostic**: Works with any OpenAI-compatible LLM server (VLLM, OpenAI API, Ollama, etc.)

## Target Use Cases

- Interactive voice assistants with customizable personalities
- Educational tools (quiz shows, explanations)
- Conversational AI demos and prototypes
- Voice-enabled applications requiring low latency

## Key Features

- Voice cloning capabilities
- Multiple deployment options (Docker Compose, Dockerless, Docker Swarm)
- Prometheus metrics and monitoring
- Development tools including subtitles and debug mode
- Multi-language support (English, French)