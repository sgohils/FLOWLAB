# FLOWLAB frontend development image.
#
# This is the Vite dev server, NOT a production image: it serves unminified
# modules with hot reload.  For a single-app deployment use the backend image
# instead (`docker compose up --build` -> http://localhost:8000), which builds
# the production bundle and serves it from the API.
#
# This image is behind `profiles: ["dev"]`, so it only starts when you ask:
#   docker compose --profile dev up
FROM node:22-alpine

# `node` (uid 1000) already exists in the base image; give the app a
# predictable home so Vite's cache and the bind-mounted sources are writable.
ENV HOME=/home/node \
    NPM_CONFIG_CACHE=/home/node/.npm

WORKDIR /app

COPY package.json package-lock.json* ./
# `npm ci` when a lockfile is present so the image matches CI exactly; fall
# back to `npm install` only for a lockfile-less checkout.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi \
    && chown -R node:node /app /home/node

USER node

EXPOSE 5173

# node:alpine has no curl, and wget is in busybox.  Poll the dev server's root
# rather than a specific asset, which may not exist yet.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD wget --spider -q http://127.0.0.1:5173/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
