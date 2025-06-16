FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS base

# Set environment variables to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    ca-certificates \
    libssl-dev \
    git \
    pkg-config \
    cmake \
    openssh-client \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

ARG GITHUB_ORG
RUN --mount=type=ssh \
    mkdir -p ~/.ssh && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    git clone git@github.com:${GITHUB_ORG}/moshi-rs.git /app \
    && cd /app \
<<<<<<< pull_from_hf -- Incoming Change
    && git checkout 3cb009cd0dbf9d573824451de272ca48f40bfb6e
=======
    && git checkout dfd0fae3f49bc53228155d9c6120f4604e1f830b
>>>>>>> staging -- Current Change

WORKDIR /app

# When starting the container for the first time, we need to compile and download
# everything, so disregarding healthcheck failure for 10 minutes is fine.
# We have a volume storing the build cache, so subsequent starts will be faster.
HEALTHCHECK --start-period=10m \
    CMD curl --fail http://localhost:8080/api/build_info || exit 1

EXPOSE 8080
ENV RUST_BACKTRACE=1

COPY . .

ENTRYPOINT ["uv", "run", "--locked", "--project", "./moshi-server", "./start_moshi_server.sh"]
