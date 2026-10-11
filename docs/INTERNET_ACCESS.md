# Making the Site Reachable from the Internet

The whole point of a website is to be reachable from **anywhere** — phone, tablet, laptop, on any network (home Wi‑Fi, cellular, office). That means the site must be reachable from the **internet**, not just your local network.

---

## What you need

| Requirement | Purpose |
|-------------|--------|
| **1. Public DNS** | So `www.probilliardssoftware.com` resolves to your server’s **public IP** for everyone on the internet. |
| **2. Port forwarding (or server has public IP)** | So traffic from the internet on ports 80 and 443 reaches the machine running Nginx (and then the API). |
| **3. Valid HTTPS certificate** | So browsers (especially on phone/tablet) trust the site. Use Let’s Encrypt (or your provider) for `www.probilliardssoftware.com`. |

If any of these is missing, the site may work on your PC (e.g. via hosts file or local DNS) but **won’t** work from the internet (e.g. phone on cellular, or someone else’s network).

---

## 1. Public DNS

Where you manage **probilliardssoftware.com** (e.g. Cloudflare, Namecheap, GoDaddy, your registrar):

- Add (or fix) an **A record**:
  - **Name/host:** `rankings-bot` (so the full name is `www.probilliardssoftware.com`)
  - **Value / points to:** Your server’s **public IP address**

Your **public IP** is the one the internet sees (e.g. from [whatismyip.com](https://whatismyip.com) on the server or your router). It is **not** a 192.0.2.10 or 10.x.x.x address (those are private).

- **Do not** point the A record to a private IP (e.g. 192.0.2.20) if you want internet access. It must point to the **public** IP of the host that will receive web traffic (see step 2).

---

## 2. Port forwarding (when the server is behind a router)

If your server (e.g. 192.0.2.20) is behind a **router** that has the public IP:

1. On the **router**, open **Port forwarding** (or **Virtual server**, **NAT**, etc.).
2. Forward:
   - **External port 80** → **Internal IP** 192.0.2.20, **port 80**
   - **External port 443** → **Internal IP** 192.0.2.20, **port 443**

So when someone on the internet goes to `https://www.probilliardssoftware.com`, their browser hits your **public IP** on port 443; the router forwards that to 192.0.2.20:443, where Nginx (or your HTTPS reverse proxy) is listening.

- The machine that receives 80/443 (here, 192.0.2.20) must be running **Nginx** (or another reverse proxy) and have the rankings-bot config so it routes to the API (e.g. on port 8003).

If the **server itself** has a public IP (e.g. a VPS), you don’t need port forwarding; just make sure Nginx is listening on 80/443 on that host and that the firewall allows 80 and 443.

---

## 3. Valid HTTPS certificate

Nginx’s config for rankings-bot uses `tls: {}`, which typically means “use the default certificate resolver.” In Nginx’s **main** config you need:

- A **certificate resolver** (e.g. Let’s Encrypt) configured.
- The rankings-bot router using that resolver so Nginx obtains and renews a cert for `www.probilliardssoftware.com`.

No certificate resolver (like Let's Encrypt) on the server is needed when using Cloudflare Tunnel.

---

## Quick checklist for internet access

| Step | Where | Action |
|------|--------|--------|
| DNS | Your DNS provider (Cloudflare, etc.) | A record `www.probilliardssoftware.com` → **public IP** |
| Ports | Router (if server is behind it) | Forward 80 → server:80, 443 → server:443 |
| HTTPS | Nginx main config | Certificate resolver (e.g. Let’s Encrypt) for the hostname |
| App | Server | API on 0.0.0.0:8003; Nginx routes hostname to it (see **DEPLOY_WEBSITE.md**) |

---

## Verify from the internet

- From a **phone on cellular** (Wi‑Fi off): open **https://www.probilliardssoftware.com**. If it loads, the site is reachable from the internet.
- From another network (e.g. a friend’s Wi‑Fi, or a VPN to a different region): same URL should work.

If it only works on your home Wi‑Fi, DNS or port forwarding is still wrong (e.g. DNS points to private IP, or ports 80/443 are not forwarded to the server).
