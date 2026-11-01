# Frontend build. There is no runtime stage: the output is static files that
# the host nginx serves, so this image exists only to produce /dist.
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
# Playwright is a dev tool for the screenshot script; the image only needs to
# run vite build, and downloading three browsers here would add ~400 MB and a
# network dependency to every deploy.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm ci

COPY . .
# Same origin in production, so the API is reached at a relative /api and there
# is no build-time API URL to get wrong per environment.
RUN npm run build
