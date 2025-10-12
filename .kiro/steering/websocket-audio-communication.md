# WebSocket Audio Communication Protocol

## Overview

Unmute uses a WebSocket-based protocol for real-time bidirectional audio communication between the frontend and backend. The protocol is based on the OpenAI Realtime API with Unmute-specific extensions.

## Connection Setup

### Frontend Connection
- **Endpoint**: `ws://localhost:8000/v1/realtime` (or backend URL + `/v1/realtime`)
- **Protocol**: `"realtime"` subprotocol required
- **Library**: `react-use-websocket` for WebSocket management

### Backend Acceptance
- Backend accepts WebSocket with `subprotocol="realtime"`
- Health check performed before allowing connections
- Maximum concurrent connections limited by semaphore (default: 4)

## Audio Processing Pipeline

### Frontend Audio Capture

1. **Microphone Access**
   ```typescript
   // Request microphone permission
   const mediaStream = await navigator.mediaDevices.getUserMedia({
     audio: {
       echoCancellation: true,
       noiseSuppression: false,
       autoGainControl: true,
       channelCount: 1
     }
   });
   ```

2. **Opus Encoding**
   - Uses `opus-recorder` library for real-time encoding
   - Sample rate: 24kHz (encoder) → 48kHz (Opus internal)
   - Frame size: 20ms
   - Channels: Mono (1 channel)
   - Complexity: 0 (fastest encoding)
   - Application: 2049 (VoIP optimized)

3. **Base64 Encoding**
   ```typescript
   const base64EncodeOpus = (opusData: Uint8Array) => {
     let binary = "";
     for (let i = 0; i < opusData.byteLength; i++) {
       binary += String.fromCharCode(opusData[i]);
     }
     return window.btoa(binary);
   };
   ```

### Backend Audio Processing

1. **Message Reception**
   ```python
   # Receive WebSocket message
   message_raw = await websocket.receive_text()
   message = ClientEventAdapter.validate_json(message_raw)
   ```

2. **Opus Decoding**
   ```python
   if isinstance(message, ora.InputAudioBufferAppend):
       opus_bytes = base64.b64decode(message.audio)
       pcm = await asyncio.to_thread(opus_reader.append_bytes, opus_bytes)
       if pcm.size:
           await handler.receive((SAMPLE_RATE, pcm[np.newaxis, :]))
   ```

3. **Audio Processing Chain**
   - STT (Speech-to-Text) service processes PCM audio
   - LLM generates text response
   - TTS (Text-to-Speech) synthesizes audio response

## Message Protocol

### Client → Server Messages

#### Audio Input
```json
{
  "type": "input_audio_buffer.append",
  "audio": "base64-encoded-opus-data"
}
```

#### Session Configuration
```json
{
  "type": "session.update",
  "session": {
    "instructions": "system prompt or character config",
    "voice": "voice_name",
    "allow_recording": true
  }
}
```

### Server → Client Messages

#### Audio Response
```json
{
  "type": "response.audio.delta",
  "delta": "base64-encoded-opus-data"
}
```

#### Transcription
```json
{
  "type": "conversation.item.input_audio_transcription.delta",
  "delta": "transcribed text chunk",
  "start_time": 1234.56
}
```

#### Text Response
```json
{
  "type": "response.text.delta",
  "delta": "LLM response text chunk"
}
```

#### Speech Detection
```json
{
  "type": "input_audio_buffer.speech_started"
}
```
```json
{
  "type": "input_audio_buffer.speech_stopped"
}
```

#### Errors
```json
{
  "type": "error",
  "error": {
    "type": "warning|fatal",
    "message": "Error description"
  }
}
```

## Frontend Audio Playback

### Opus Decoding
```typescript
// Decode base64 Opus data
const opus = base64DecodeOpus(data.delta);

// Send to Web Worker for decoding
audioProcessor.decoder.postMessage({
  command: "decode",
  pages: opus
}, [opus.buffer]);
```

### Audio Output
- Uses Web Audio API `AudioWorkletNode` for low-latency playback
- Decoded PCM audio fed to output worklet
- Connected to both speakers and recording destination

## Key Technical Details

### Audio Specifications
- **Sample Rate**: 24kHz (processing) / 48kHz (Opus internal)
- **Channels**: Mono (1 channel)
- **Codec**: Opus with streaming pages
- **Frame Size**: 20ms chunks
- **Encoding**: Base64 over WebSocket JSON messages

### Latency Optimizations
- **Streaming**: Audio processed in small chunks (20ms frames)
- **Parallel Processing**: STT, LLM, and TTS run concurrently when possible
- **GPU Acceleration**: All ML models run on GPU
- **Minimal Buffering**: Direct WebSocket streaming without intermediate storage

### Error Handling
- **Connection Loss**: Automatic cleanup of audio resources
- **Service Failures**: Graceful degradation with user notification
- **Audio Errors**: Robust handling of codec and device issues

### Security Considerations
- **CORS**: Configured for local development origins
- **Microphone Permission**: Required before connection
- **HTTPS**: Required for microphone access (except localhost)
- **Recording Consent**: User consent required for session recording

## Development Notes

### Testing Audio Flow
```bash
# Test WebSocket connection
uv run unmute/loadtest/loadtest_client.py --server-url ws://localhost:8000 --n-workers 1

# Monitor audio processing
# Enable dev mode in frontend (press 'D') to see debug info
```

### Common Issues
- **Microphone Access**: Requires HTTPS or localhost
- **Opus Compatibility**: Ensure proper Web Worker loading
- **Buffer Underruns**: Check for adequate GPU memory
- **Connection Drops**: Monitor WebSocket state changes