# This is the public-facing version.
FROM nvidia/cuda:12.8.1-devel-ubuntu22.04 AS base

# Set environment variables to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies, including dos2unix to handle Windows line endings
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    ca-certificates \
    libssl-dev \
    git \
    pkg-config \
    cmake \
    wget \
    openssh-client \
    dos2unix \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

WORKDIR /app

# When starting the container for the first time, we need to compile and download
# everything, so disregarding healthcheck failure for 10 minutes is fine.
# We have a volume storing the build cache, so subsequent starts will be faster.
HEALTHCHECK --start-period=10m \
    CMD curl --fail http://localhost:8080/api/build_info || exit 1

EXPOSE 8080
ENV RUST_BACKTRACE=1

RUN wget https://raw.githubusercontent.com/kyutai-labs/moshi/bf359af7694add34c13e65d2f009f0cb474d87cc/rust/moshi-server/pyproject.toml
RUN wget https://raw.githubusercontent.com/kyutai-labs/moshi/bf359af7694add34c13e65d2f009f0cb474d87cc/rust/moshi-server/uv.lock

COPY . .

# Ensure the startup script is runnable inside the container.
# This prevents script errors that can happen if the project was cloned on Windows,
# which uses a different text file format (CRLF) than the Linux environment in the container (LF).
RUN dos2unix ./start_moshi_server_public.sh && chmod +x ./start_moshi_server_public.sh

ENTRYPOINT ["uv", "run", "--locked", "--project", "./moshi-server", "./start_moshi_server_public.sh"]
