# Kaihle Frontend - React + Vite Development Server
FROM node:20-alpine

# Set environment variables
ENV NODE_ENV=development

# Set work directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy frontend source
COPY . .

# Expose port 5173
EXPOSE 5173

# Run vite dev server with host 0.0.0.0 for external access
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
