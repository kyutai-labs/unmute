FROM ghcr.io/astral-sh/uv:0.6.17-debian AS build
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LOCKED=1

RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv run --no-dev echo hello

COPY . .
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --start-period=15s \
    CMD curl --fail http://localhost:80/metrics || exit 1

FROM build AS production
# Production target for regular websocket server
CMD ["uv", "run", "--no-dev", "uvicorn", "unmute.main_websocket:app", "--host", "0.0.0.0", "--port", "80", "--ws-per-message-deflate=false"]

FROM build AS autoconnect
# Production target for auto-connect backend
CMD ["uv", "run", "--no-dev", "python", "-m", "unmute.main_auto_connect"]

FROM build AS hot-reloading
# Development target with hot reloading
CMD ["uv", "run", "--no-dev", "uvicorn", "unmute.main_websocket:app", "--reload", "--host", "0.0.0.0", "--port", "80", "--ws-per-message-deflate=false"]
