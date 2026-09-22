# ── Build stage: production frontend bundle ───────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# VITE_API_URL is the browser-visible base for /api calls. In the standard
# topology the frontend and backend share an origin (nginx reverse proxies
# /api), so the default is the same-origin path. Override only when the API is
# served from a different origin (CORS + VITE_API_URL must match then).
ARG VITE_API_URL=/api
ARG VITE_DEMO_MODE=true
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE

RUN npm run build

# ── Serve stage: static files behind Nginx ────────────────────────────────────
FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Probes through the same proxy path the browser uses (nginx → backend /api/health).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD ["wget", "-qO-", "http://127.0.0.1/api/health"]