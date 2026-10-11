# Mobile and Tablet Access (Phone, iPad)

If the site works on PC but **does not load** or **shows a blank page** on phone or iPad, check the following.

---

## 1. Use the same URL on all devices

Open this exact URL on phone and iPad (same as on PC):

- **https://www.probilliardssoftware.com**

Do **not** use `http://` or an IP address (e.g. `192.0.2.20:5174`) on mobile — use the full HTTPS hostname above.

---

## 2. DNS and network

The device (phone/iPad) must be able to **resolve** and **reach** the hostname.

- **Same Wi‑Fi as the server:** If the PC is on the same LAN as the server (e.g. 192.0.2.20), the phone/iPad should use the **same Wi‑Fi**. Then the hostname must resolve on that network (e.g. via your router’s DNS or a local DNS/hosts entry that your PC uses). If only the PC has the hostname in its hosts file, the phone won’t resolve it.
- **Cellular / different network:** If the phone is on cellular (or iPad on a different Wi‑Fi), the hostname must resolve via **public DNS** and the server must be reachable from the internet (public IP or tunnel). Otherwise the browser will show “can’t connect” or “Safari could not open the page”.

**Quick check on phone/iPad:** In the browser’s address bar, go to `https://www.probilliardssoftware.com`.  
- If you see a connection error or “cannot connect” → DNS or network (hostname not resolving or server not reachable from that network).  
- If the page loads but is blank → see step 3 (cache / HTTPS).

---

## Same network but phone/iPad still can’t connect

If the site works on your PC and your phone/iPad are on the **same Wi‑Fi** but the site won’t load on phone/iPad, the usual cause is **DNS**: the hostname resolves on the PC but not on the phone/iPad.

- **Why:** The PC may have the hostname in its **hosts file** (e.g. `www.probilliardssoftware.com` → server IP), or it uses a DNS that has that record. Phones and iPads don’t use the PC’s hosts file; they use whatever DNS they get (often from the router or the device’s own DNS). If that DNS doesn’t know the hostname, the phone/iPad can’t connect.

**Fix: make the hostname resolve for everyone on the LAN**

1. **Find the server’s IP on the LAN**  
   On the server (or from the PC): `hostname -I` or `ip addr` and note the LAN IP (e.g. `192.0.2.20`).

2. **Add a local DNS record** so that `www.probilliardssoftware.com` points to that IP for all devices on your network:
   - **Router:** If your router has “Local DNS”, “DNS override”, “Custom hosts”, or “Static DNS”:
     - Add: hostname `www.probilliardssoftware.com` → IP `192.0.2.20` (use your server’s actual IP).
   - **Pi-hole / AdGuard Home / similar:** Add a local DNS (A) record: `www.probilliardssoftware.com` → server IP.
   - **No router option:** You’d need a DNS server on the LAN that has this record and that the phone/iPad use (e.g. set the Wi‑Fi network’s DNS on the phone to that server). Many home setups use the router or Pi-hole for this.

3. **On the phone/iPad:**  
   - Connect to the same Wi‑Fi.  
   - Open **https://www.probilliardssoftware.com** (use HTTPS and the full hostname, not the IP).  
   - If you still get “cannot connect”, the phone/iPad are not yet resolving the hostname (wait a minute after changing router DNS, or reboot the router; or double‑check the router’s local DNS entry).

4. **Optional check:** From the PC, run:  
   `ping www.probilliardssoftware.com`  
   You should see the server’s LAN IP. On the phone you can’t easily ping, but once the router (or Pi-hole) has the record, the browser will resolve it too.

---

## 3. Cache and HTTPS

- **Hard refresh / clear cache:** On the phone or iPad, try:
  - **Private / Incognito** window, or  
  - **Clear site data** for `www.probilliardssoftware.com` (browser settings → Site settings / Storage → Clear), then open the URL again.
- **HTTPS certificate:** Mobile Safari (and Chrome on iOS) are strict about certificates. If the site uses a **self‑signed** or invalid cert, the browser may block the page. Use a valid certificate for `www.probilliardssoftware.com` (e.g. Let’s Encrypt (e.g. via Cloudflare or Nginx)) so phone and iPad trust the connection.

---

## 4. After fixing server or DNS

1. **Restart the API** so it serves the latest frontend and headers (see **docs/START_STOP_RESTART.md**).
2. On phone/iPad: open **https://www.probilliardssoftware.com** in a **new private window** or after clearing site data, then reload.

---

## Summary

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| “Can’t connect” / “Could not open” on phone/iPad | DNS or network: hostname not resolving or server not reachable | Use same Wi‑Fi as PC, or set up public DNS + reachable server |
| Blank/white page on phone/iPad | Cache or old response | Private window; clear site data; restart API and reload |
| “Connection not private” / cert warning | Invalid or self‑signed HTTPS cert | Use a valid cert for the hostname (e.g. Let’s Encrypt) |

The site is built to be **responsive** (layout works on phone and tablet). Once the page loads, rankings and navigation should work the same as on PC.
