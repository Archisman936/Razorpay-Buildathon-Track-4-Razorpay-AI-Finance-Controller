# ==============================================================================
# Razorpay AI Finance Controller - Frontend Dockerfile
# ==============================================================================
# Multi-stage build: Node 20 for Vite build + Nginx Alpine for serving
# ==============================================================================

# --- Stage 1: Build static bundle ---
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests and install packages
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code and build production bundle
COPY . .
RUN npm run build

# --- Stage 2: Production Nginx Server ---
FROM nginx:alpine

# Remove default static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built distribution from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy Nginx configuration template (supports BACKEND_URL environment variable)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Default backend URL and filter so envsubst only replaces BACKEND_URL (preserving $uri, $host, etc.)
ENV BACKEND_URL="http://backend:8000" \
    NGINX_ENVSUBST_FILTER="BACKEND_URL"

# Expose standard HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Launch Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
