# syntax=docker.io/docker/dockerfile:1

FROM node:18-alpine AS dev

# Install required dependencies
RUN apk add --no-cache libc6-compat curl

# Set working directory
WORKDIR /app

# Install dependencies using the package manager (detected automatically via lockfile)
COPY package.json tsconfig.json yarn.lock* package-lock.json* pnpm-lock.yaml* .npmrc* postcss.config.mjs ./
COPY public/ ./public/
RUN corepack enable pnpm && pnpm i --frozen-lockfile

# Expose the port the dev server runs on
EXPOSE 3000

# Set environment variables
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
ENV NEXT_PUBLIC_IN_DOCKER=true

HEALTHCHECK --start-period=15s \
    CMD curl --fail http://localhost:3000/ || exit 1

# The source code will be mounted as a volume, so no need to copy it here
# Default command to run the development server with hot reloading
CMD ["pnpm", "dev"]
