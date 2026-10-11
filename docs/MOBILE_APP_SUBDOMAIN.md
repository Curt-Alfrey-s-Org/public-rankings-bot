# Mobile App on Subdomain

The Expo web app is served at **app.probilliardssoftware.com** (no "bot" in the public URL). Same API as main site. Android/iOS use that API too.

## Build and deploy

1. Build web app (from workspace root): cd mobile && EXPO_PUBLIC_API_URL=https://www.probilliardssoftware.com npx expo export --platform web
2. Restart Nginx: cd Rankings-Bot && docker stop probilliards-nginx && docker rm probilliards-nginx && docker-compose -f nginx-config/docker-compose.nginx.yml up -d --build
3. Cloudflare Tunnel: Public hostname **app.probilliardssoftware.com** → http://probilliards-nginx:80 (same as main site).

Config: nginx-config/rankings-bot-cloudflare-docker.conf (second server block; mobile at app.probilliardssoftware.com).
