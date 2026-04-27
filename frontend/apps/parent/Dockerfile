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
COPY apps/parent/package.json ./apps/parent/package.json
COPY packages ./packages

# Install dependencies from lockfile (frozen — no version drift)
RUN pnpm install --frozen-lockfile

# Copy application source
COPY apps/parent ./apps/parent

# Build the static bundle
RUN pnpm --filter parent build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────
FROM nginx:stable-alpine

# Copy built assets
COPY --from=builder /app/apps/parent/dist /usr/share/nginx/html

# nginx config: serve on 3003, route all paths to index.html (SPA)
RUN printf 'server {\n\
    listen 3003;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # Security headers\n\
    add_header X-Content-Type-Options "nosniff" always;\n\
    add_header X-Frame-Options "DENY" always;\n\
    add_header X-XSS-Protection "1; mode=block" always;\n\
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;\n\
\n\
    # Cache static assets with hash\n\
    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n\
' > /etc/nginx/conf.d/default.conf

EXPOSE 3003

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3003/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
