# ============================================================================
# PRODUCTION BUILD
# Stage 1: build the static bundle
# Stage 2: serve with nginx
# For local Docker dev, use Dockerfile.dev instead
# ============================================================================

# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

RUN npm install -g pnpm

# Copy workspace manifest files first (layer caching)
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/teacher/package.json ./apps/teacher/package.json
COPY packages ./packages

# Install dependencies from lockfile (frozen — no version drift)
RUN pnpm install --frozen-lockfile

# Copy application source
COPY apps/teacher ./apps/teacher

# Build the static bundle
RUN pnpm --filter teacher build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────
FROM nginx:stable-alpine

# Copy built assets
COPY --from=builder /app/apps/teacher/dist /usr/share/nginx/html

# nginx config: serve on 3001, route all paths to index.html (SPA)
RUN printf 'server {\n\
    listen 3001;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n\
' > /etc/nginx/conf.d/default.conf

EXPOSE 3001

CMD ["nginx", "-g", "daemon off;"]
