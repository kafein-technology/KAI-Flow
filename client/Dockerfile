# 1. Bağımlılıkların kurulumu (prod ve dev)
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# 2. Uygulama dosyaları ve build
FROM node:22-alpine AS build
WORKDIR /app

#  Build-time env değişkenleri tanımlanıyor
ARG VITE_API_BASE_URL
ARG VITE_API_VERSION
ARG VITE_BASE_PATH
ARG VITE_NODE_ENV
ARG VITE_ENABLE_LOGGING

#  Build ortamına geçiriliyor
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_VERSION=$VITE_API_VERSION
ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_NODE_ENV=$VITE_NODE_ENV
ENV VITE_ENABLE_LOGGING=$VITE_ENABLE_LOGGING

COPY . .
COPY --from=deps /app/node_modules ./node_modules

#  Build sırasında env'ler gömülmüş olacak
RUN npm run build

# 3. Prod sunucu - Using 'serve' for static file serving
FROM node:22-alpine AS production
WORKDIR /app

# Install serve globally for static file serving (vite is dev-only)
RUN npm install -g serve

# Copy built assets from build stage
COPY --from=build /app/dist ./dist
COPY --from=build /app/public/config.js ./dist/config.js

# Copy entrypoint script for runtime config generation
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["serve", "-s", "dist", "-l", "3000"]
