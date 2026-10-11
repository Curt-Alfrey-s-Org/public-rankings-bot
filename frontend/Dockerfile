FROM node:20-alpine AS builder

WORKDIR /app

ARG NPM_REGISTRY=http://192.0.2.30:4873

COPY package*.json ./
# package.json depends on file:vendor/alfa-ai-chat-widget-*.tgz; npm ci needs it before COPY . .
# (only worked while the BuildKit npm cache still held the tarball).
COPY vendor/ ./vendor/
RUN --mount=type=cache,id=bots-npm,target=/root/.npm,sharing=locked \
    npm ci --registry "${NPM_REGISTRY}" --prefer-offline --no-audit --no-fund

COPY . .
ENV VITE_API_URL=
ENV VITE_WS_URL=
RUN npm run build

FROM nginx:1.30-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO /dev/null http://localhost/ || exit 1
