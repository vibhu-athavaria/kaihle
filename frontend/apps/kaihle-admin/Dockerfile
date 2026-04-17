FROM node:20-alpine

WORKDIR /app

# Install pnpm globally
RUN npm install -g pnpm

# Copy package files for dependency resolution
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/kaihle-admin/package.json ./apps/kaihle-admin/package.json
COPY packages ./packages

# Install ALL workspace dependencies (freezes versions from lock file)
RUN pnpm install --config.confirmModulesPurge=false

# Copy the rest of the application
COPY apps ./apps
COPY packages ./packages

# Clear Vite cache to avoid stale build issues
RUN find . -type d -name ".vite" -exec rm -rf {} + 2>/dev/null || true

EXPOSE 3005

# Run in development mode with hot reload
CMD ["pnpm", "dev:kaihle-admin"]
