# Nginx container for Rankings Bot behind Cloudflare Tunnel (cf-probilliards).
# Tunnel route: www.probilliardssoftware.com → http://probilliards-nginx:80
# Switch main site: maintenance vs production (demo) via ./scripts/switch-site.sh
#
# Doc refs (AI / maintainers): docs/NETWORKING_DOC_HOOKS.md; docs/CLOUDFLARE_TUNNEL_NGINX.md;
#   docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md; nginx-config/README.md
FROM nginx:1.25.5-alpine
RUN apk add --no-cache curl
RUN mkdir -p /etc/nginx/templates
COPY rankings-bot-maintenance.conf /etc/nginx/templates/maintenance.conf
COPY rankings-bot-production.conf /etc/nginx/templates/production.conf
COPY rankings-bot-maintenance.conf /etc/nginx/conf.d/default.conf
COPY maintenance /var/www/maintenance
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/ -o /dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
