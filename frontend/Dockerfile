# Multi-stage build for Railway deployment
# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Set production environment
ENV NODE_ENV=production

# Build the application
# VITE_API_URL will be set at build time via Railway
ARG VITE_API_URL
ARG VITE_SENTRY_DSN
ARG VITE_APP_ENV=production

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
ENV VITE_APP_ENV=$VITE_APP_ENV

RUN npm run build

# Production stage - serve static files
FROM nginx:alpine AS production

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
