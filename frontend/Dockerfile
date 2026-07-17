# syntax=docker/dockerfile:1
#
# Web image for AI Smart Notes: a multi-stage build that compiles the Vite/React
# SPA in Node, then serves the static output with a tiny nginx image.

# --- Stage 1: build the production bundle -----------------------------
FROM node:22-alpine AS build
WORKDIR /app

# The browser talks to the SAME origin it was served from; nginx proxies
# /api/v1 and /media to the api container. Vite inlines VITE_* variables at
# BUILD time, so this must be set before `npm run build`. Overridable via
# build-arg for a deployment that hosts the API elsewhere.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Install deps from the lockfile first (cached until the lockfile changes).
COPY package.json package-lock.json ./
RUN npm ci

# Copy sources and build. `npm run build` runs `tsc -b && vite build`, so a
# type error fails the image build — the container can't ship broken types.
COPY . .
RUN npm run build

# --- Stage 2: serve with nginx ----------------------------------------
FROM nginx:alpine AS serve

# Our SPA-fallback + reverse-proxy config replaces nginx's default site.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Only the built static assets travel to the final image — no Node, no
# node_modules, no source. This keeps the web image small.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
# The base nginx image already runs the server in the foreground; no CMD needed.
