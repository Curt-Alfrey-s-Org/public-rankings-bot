# App steps (install from where, to where)

Do in order. **Server is Linux** — all commands below are on the Linux server (SSH or local terminal).

---

## 1. Node.js (on the Linux server)

- FROM: On the server, install Node (e.g. `sudo apt update && sudo apt install -y nodejs npm` on Debian/Ubuntu, or use NodeSource/nvm). Or from https://nodejs.org get the Linux binary and unpack to e.g. /usr/local.
- TO: Installed on the server. CHECK: Open a terminal (SSH into the server or Ctrl+Alt+T). Type: `node -v` . You should see e.g. v20.x.x .

---

## 2. Expo Go (on your phone)

- FROM: iPhone App Store or Android Play Store. Search: Expo Go.
- TO: Tap Get/Install. Wait. App appears on home screen.

---

## 3. Project folder (on the Linux server)

- WHERE: The rankings-bot repo on the server (e.g. /home/ansible/rankings-bot or ~/rankings-bot). Inside it there is a folder named mobile.
- OPEN TERMINAL on the server (SSH or local). Type: `cd` then space then path to mobile. Example: `cd /home/ansible/rankings-bot/mobile` or `cd ~/rankings-bot/mobile` .
- Press Enter. You are now "in" the mobile folder.

---

## 4. Dependencies (one time)

- WHERE TO TYPE: Same terminal, must be in mobile folder.
- Type: npm install
- Press Enter. Wait 1-2 min. Done when the prompt returns.

---

## 5. Start the app

- WHERE TO TYPE: Same terminal, in mobile folder.
- Type: npm start
- Press Enter. A browser opens WITH A QR CODE. Leave it open.

---

## 6. Open on phone

- Phone and computer: SAME Wi-Fi.
- iPhone: Open Camera, point at QR code on screen, tap the banner, opens in Expo Go.
- Android: Open Expo Go, tap Scan QR code, point at QR code.
- App loads on phone.

---

## 7. Log in

- Username and password: same as the website (e.g. user / user123). Tap Sign In.

---

## If you see Network error

- Check phone and server are on same Wi-Fi (or the app is using the public API URL).
- If the app must talk to this server: on the server, find its IP (e.g. `hostname -I` or `ip addr`). In the terminal on the server, in the mobile folder, BEFORE `npm start`, type (use the server IP): `export EXPO_PUBLIC_API_URL=http://YOUR_SERVER_IP:8003` . Then type `npm start` again. Scan QR again.

---

## Build installable app (later)

- Sign up at https://expo.dev (free).
- In terminal (any folder): npm install -g eas-cli . Then: eas login (use Expo account).
- In terminal, go to mobile folder. Type: eas build:configure (accept defaults).
- Android: eas build --platform android --profile preview . Wait. You get a LINK. Open link, download APK. Copy APK to phone, open it, install (allow unknown sources if asked).
- iPhone: Need Apple Developer $99/year. Then eas build --platform ios --profile preview . Follow prompts.
