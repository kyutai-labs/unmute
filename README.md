# Unmute

Try it out at [Unmute.sh](https://unmute.sh)!

Unmute is a system that allows text LLMs to listen and speak by wrapping them in Kyutai's Text-to-speech and Speech-to-text models.
The speech-to-text transcribes what the user says, the LLM generates a response in text, and the text-to-speech reads it out loud.
Both the STT and TTS are optimized for low latency and the system works with any text LLM you like.

If you want to use Kyutai STT or Kyutai TTS separately, check out [kyutai-labs/delayed-streams-modeling](https://github.com/kyutai-labs/delayed-streams-modeling).

On a high level, it works like this:

```mermaid
graph LR
    UB[User browser]
    UB --> B(Backend)
    UB --> F(Frontend)
    B --> STT(Speech-to-text)
    B --> LLM(LLM)
    B --> TTS(Text-to-speech)
```

- The user opens the Unmute website, served by the **frontend**.
- By clicking "connect", the user establishes a websocket connection to the **backend**, sending audio and other metadata back and forth in real time.
  - The backend connects via websocket to the **speech-to-text** server, sending it the audio from the user and receiving back the transcription in real time.
  - Once the speech-to-text detects that the user has stopped speaking and it's time to generate a response, the backend connects to an **LLM** server to retrieve the response. We host our own LLM using [VLLM](https://github.com/vllm-project/vllm), but you could also use an external API like OpenAI or Mistral.
  - As the response is being generated, the backend feeds it to the **text-to-speech** server to read it out loud, and forwards the generated speech to the user.

## Setup

> [!NOTE]
> If something isn't working for you, don't hesistate to open an issue. We'll do our best to help you figure out what's wrong.

Requirements:
- Hardware: a GPU with CUDA support and at least 16 GB memory.
- OS: Linux, or Windows with WSL ([installation instructions](https://ubuntu.com/desktop/wsl)). Running on Windows natively is not supported (see [#84](https://github.com/kyutai-labs/unmute/issues/84)). Neither is running on Mac (see [#74](https://github.com/kyutai-labs/unmute/issues/74)).

We provide multiple ways of deploying your own [unmute.sh](unmute.sh):

| Name                      | Number of gpus | Number of machines | Difficulty | Documented | Kyutai support |
|---------------------------|----------------|--------------------|------------|------------|----------------|
| Docker Compose            | 1+             | 1                  | Very easy  |✅         |✅              |
| Dockerless                | 1 to 3         | 1 to 5             | Easy       |✅         |✅              |
| Docker Swarm              | 1 to ~100      | 1 to ~100          | Medium     |✅         |❌              |


Since Unmute is a complex system with many services that need to be running at the same time, we recommend using [**Docker Compose**](https://docs.docker.com/compose/) to run Unmute.
It allows you to start or stop all services using a single command.
Since the services are Docker containers, you get a reproducible environment without having to worry about dependencies.

While we support deploying with Docker compose and without Docker, the Docker Swarm deployment is only given to show how we deploy and scale [unmute.sh](unmute.sh). It looks a lot like the compose files, but since debugging multi-nodes applications is hard, we cannot help you debug the swarm deployment.

### LLM access on Hugging Face Hub

You can use any LLM you want.
By default, Unmute uses [Mistral Small 3.2 24B](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) as the LLM.
([Gemma 3 12B](https://huggingface.co/google/gemma-3-12b-it) is also a good choice.)
This model is freely available but requires you to accept the conditions to accept it:

1. Create a Hugging Face account.
2. Accept the conditions on the [Mistral Small 3.2 24B model page](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506).
3. [Create an access token.](https://huggingface.co/docs/hub/en/security-tokens) You can use a fine-grained token, the only permission you need to grant is "Read access to contents of all public gated repos you can access".
   **Do not use tokens with write access when deploying publicly.** In case the server is compromised somehow, the attacker would get write access to any models/datasets/etc. you have on Hugging Face.
4. Add the token into your `~/.bashrc` or equivalent as `export HUGGING_FACE_HUB_TOKEN=hf_...your token here...`

### Start Unmute

Make sure you have [**Docker Compose**](https://docs.docker.com/compose/) installed.
You'll also need the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) to allow Docker to access your GPU.
To make sure the NVIDIA Container Toolkit is installed correctly, run:
```bash
sudo docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

If you use [meta-llama/Llama-3.2-1B](https://huggingface.co/meta-llama/Llama-3.2-1B),
the default in `docker-compose.yml`, 16GB of GPU memory is sufficient.
If you're running into memory issues, open `docker-compose.yml` and look for `NOTE:` comments to see places that you might need to adjust.

On a machine with a GPU, run:

```bash
# Make sure you have the environment variable with the token:
echo $HUGGING_FACE_HUB_TOKEN  # This should print hf_...something...

docker compose up --build
```

#### Using multiple GPUs

On [Unmute.sh](https://unmute.sh/), we run the speech-to-text, text-to-speech, and the VLLM server on separate GPUs,
which improves the latency compared to a single-GPU setup.
The TTS latency decreases from ~750ms when running everything on a single L40S GPU to around ~450ms on [Unmute.sh](https://unmute.sh/).

If you have at least three GPUs available, add this snippet to the `stt`, `tts` and `llm` services to ensure they are run on separate GPUs:

```yaml
  stt: # Similarly for `tts` and `llm`
    # ...other configuration
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```


### Running without Docker

Alternatively, you can choose to run Unmute by manually starting the services without going through Docker.
This can be more difficult to set up because of the various dependencies needed.

The following instructions only work for Linux and WSL.

#### Software requirements

* `uv`: Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
* `cargo`: Install with `curl https://sh.rustup.rs -sSf | sh`
* `pnpm`: Install with `curl -fsSL https://get.pnpm.io/install.sh | sh -`
* `cuda 12.1`: Install it with conda or directly from the Nvidia website. Needed for the Rust processes (tts and stt).

#### Hardware requirements

Start each of the services one by one in a different tmux session or terminal:
```bash
./dockerless/start_frontend.sh
./dockerless/start_backend.sh
./dockerless/start_llm.sh        # Needs 6.1GB of vram
./dockerless/start_stt.sh        # Needs 2.5GB of vram
./dockerless/start_tts.sh        # Needs 5.3GB of vram
```
And the website should be accessible at `http://localhost:3000`.

### Connecting to a remote server running Unmute

If you're running Unmute on a machine that you're accessing over SSH – call it `unmute-box`  – and you'd like to access it from your local computer,
you'll need to set up [port forwarding](https://www.ssh.com/academy/ssh/tunneling-example).

**For Docker Compose**: By default, our Docker Compose setup runs on port 80.
To forward port 80 on the remote to port 3333 locally, use:

```bash
ssh -N -L 3333:localhost:80 unmute-box
```
If everything works correctly, this command will simply not output anything and just keep running.
Then open `localhost:3333` in your browser.

**For Dockerless**: You need to separately forward the backend (port 8000) and frontend (port 3000):

```bash
ssh -N -L 8000:localhost:8000 -L 3000:localhost:3000 unmute-box
```

```mermaid
flowchart LR
    subgraph Local_Machine [Local Machine]
        direction TB
        browser[Browser]
        browser -. "User opens localhost:3000 in browser" .-> local_frontend[localhost:3000]
        browser -. "Frontend queries API at localhost:8000" .-> local_backend[localhost:8000]
    end
    subgraph Remote_Server [Remote Server]
        direction TB
        remote_backend[Backend:8000]
        remote_frontend[Frontend:3000]
    end
    local_backend -- "SSH Tunnel: 8000" --> remote_backend
    local_frontend -- "SSH Tunnel: 3000" --> remote_frontend
```

### HTTPS support

For simplicity, we omit HTTPS support from the Docker Compose and Dockerless setups.
If you want to make the deployment work over the HTTPS, consider using Docker Swarm
(see [SWARM.md](/SWARM.md)) or ask your favorite LLM how to make the Docker Compose or dockerless setup work over HTTPS.


## Production deployment with Docker Swarm

If you're curious to know how we deploy and scale [unmute.sh](https://unmute.sh), take a look at our docs
on the [Docker Swarm deployment](./SWARM.md).

## Modifying Unmute

Here are some high-level pointers about how you'd go about making certain changes to Unmute.

### Subtitles and dev mode

Press "S" to turn on subtitles for both the user and the chatbot.

There is also a dev mode that can help debugging, but it's disabled by default.
Go to `useKeyboardShortcuts.ts` and change `ALLOW_DEV_MODE` to `true`.
Then press `D` to see a debug view.
You can add information to the dev mode by modifying `self.debug_dict` in `unmute_handler.py`.

### Changing characters/voices

The characters' voices and prompts are defined in [`voices.yaml`](voices.yaml).
The format of the config file should be intuitive.
Certain system prompts contain dynamically generated elements.
For example, "Quiz show" has its 5 questions randomly chosen in advance from a fixed list.
System prompts like this are defined in [`unmute/llm/system_prompt.py`](unmute/llm/system_prompt.py).

Note that the file is only loaded when the backend starts and is then cached, so if you change something in `voices.yaml`,
you'll need to restart the backend.

### Using external LLM servers

The Unmute backend can be used with any OpenAI compatible LLM server. By default, the `docker-compose.yml` configures VLLM to enable a fully self-contained, local setup.
You can modify this file to change to another external LLM, such as an OpenAI server, a local ollama setup, etc.

For ollama, as environment variables for the `unmute-backend` image, replace
```yaml
  backend:
    image: unmute-backend:latest
    [..]
    environment:
      [..]
       - KYUTAI_LLM_URL=http://llm:8000
```

with
```yaml
  backend:
    image: unmute-backend:latest
    [..]
    environment:
      [..]
      - KYUTAI_LLM_URL=http://host.docker.internal:11434
      - KYUTAI_LLM_MODEL=gemma3
      - KYUTAI_LLM_API_KEY=ollama
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
This points to your localhost server. Alternatively, for OpenAI, you can use
```yaml
  backend:
    image: unmute-backend:latest
    [..]
    environment:
      [..]
      - KYUTAI_LLM_URL=https://api.openai.com/v1
      - KYUTAI_LLM_MODEL=gpt-4.1
      - KYUTAI_LLM_API_KEY=sk-..
```

The section for vllm can then be removed, as it is no longer needed:
```yaml
  llm:
    image: vllm/vllm-openai:v0.9.1
    [..]
```

### Swapping the frontend

The backend and frontend communicate over websocket using a protocol based on the
[OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime) ("ORA").
Where possible, we try to match the ORA format, but there are some extra messages we needed to add,
and others have simplified parameters.
We try to make it clear where we deviate from the ORA format, see [`unmute/openai_realtime_api_events.py`](unmute/openai_realtime_api_events.py).

For detailed information about the WebSocket communication protocol, message types, and audio processing pipeline, see the [browser-backend communication documentation](docs/browser_backend_communication.md).

Ideally, it should be simple to write a single frontend that can communicate with either the Unmute backend
or the OpenAI Realtime API, but we are not fully compatible yet.
Contributions welcome!

The frontend is a Next.js app defined in `frontend/`.
If you'd like to compare to a different frontend implementation,
there is a Python client defined in
[`unmute/loadtest/loadtest_client.py`](unmute/loadtest/loadtest_client.py),
a script that we use to benchmark the latency and throughput of Unmute.

### Tool calling

This is a common requirement so we would appreciate a contribution to support tool calling in Unmute!

The easiest way to integrate tool calling into Unmute would be to do so in a way that's fully invisible to Unmute itself - just make it part of the LLM server.
See [this comment](https://github.com/kyutai-labs/unmute/issues/77#issuecomment-3035220686) on how this can be achieved.
You'd need to write a simple server in FastAPI to wrap vLLM but plug in the tool call responses.

## Developing Unmute

### Install pre-commit hooks

First install `pre-commit` itself – you likely want to install it globally using `pip install pre-commit` rather than in a virtual environment or `uv`,
because you need the `pre-commit` executable to always be available. Then run:

```bash
pre-commit install --hook-type pre-commit
```

We recommend using [uv](https://docs.astral.sh/uv/) to manage Python dependencies.
The commands below assume you are using uv.

### Run backend (dev mode, with autoreloading)

```bash
uv run fastapi dev unmute/main_websocket.py
```

### Run backend (production)

```bash
uv run fastapi run unmute/main_websocket.py
```

### Run loadtest

`loadtest_client.py` is a script that connects to Unmute and simulates conversations with it in order to measure latency and throughput.

```bash
uv run unmute/loadtest/loadtest_client.py --server-url ws://localhost:8000 --n-workers 16
```
