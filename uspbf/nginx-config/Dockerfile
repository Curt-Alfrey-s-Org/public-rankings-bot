# USPBF Nginx — example.com + app.example.com. Default: maintenance page on apex/www.
# Switch: ./scripts/switch-site.sh production | maintenance (no rebuild).
# BOT_API_KEY is injected into the static-site /api/ allowlist via docker-entrypoint.d (never in browser);
# the container refuses to start if BOT_API_KEY is unset. snippets/ holds the shared proxy/allowlist config.
FROM nginx:alpine
RUN apk add --no-cache curl
RUN mkdir -p /etc/nginx/templates /etc/nginx/snippets
COPY snippets/ /etc/nginx/snippets/
COPY bot-api-key-headers.conf.template /etc/nginx/bot-api-key-headers.conf.template
COPY docker-entrypoint.d/99-uspbf-bot-api-key.sh /docker-entrypoint.d/99-uspbf-bot-api-key.sh
RUN chmod +x /docker-entrypoint.d/99-uspbf-bot-api-key.sh
COPY uspbf-nginx-maintenance.conf /etc/nginx/templates/maintenance.conf
COPY uspbf-nginx-production.conf /etc/nginx/templates/production.conf
COPY uspbf-nginx-maintenance.conf /etc/nginx/conf.d/default.conf
COPY maintenance /var/www/maintenance
COPY site /var/www/site
EXPOSE 80 8080 8089
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health -o /dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
