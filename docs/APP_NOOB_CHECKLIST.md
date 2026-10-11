# App checklist (step-by-step, very specific)

Do the steps in order. Each step says **from where** and **to where**. **Server is Linux** — all terminal steps are on the Linux server (SSH or local).

---

## Part 1: Run the app on your phone

### Step 1: Install Node.js on the Linux server

- **From:** The server (Linux). Install Node (e.g. `sudo apt update && sudo apt install -y nodejs npm` on Debian/Ubuntu).
- **Check:** Open a terminal on the server (SSH or Ctrl+Alt+T). Type `node -v` and press Enter. You should see e.g. `v20.x.x`.

---

### Step 2: Install Expo Go on your phone

- **From:** Your phone.
- **iPhone:** Open **App Store**. Tap the search icon. Type `Expo Go`. Tap the app **Expo Go** by “Expo”. Tap **Get** (or the cloud icon). Wait until it installs. The app appears on your home screen.
- **Android:** Open **Play Store**. Tap the search bar. Type `Expo Go`. Tap the app **Expo Go** by “Expo”. Tap **Install**. Wait until it installs. The app appears in your app drawer or home screen.

---

### Step 3: Go to the project folder on the server

- **Where the project is:** The rankings-bot repo on the Linux server (e.g. `/home/ansible/rankings-bot`). Inside it there is a folder named `mobile`. You do the next steps **inside** `mobile`.

**In the terminal on the server:** Type `cd` and a space, then the path to `mobile`. Example: `cd /home/ansible/rankings-bot/mobile` or `cd ~/rankings-bot/mobile`.

- Press Enter. The next line should show that you’re now “in” that folder (e.g. the prompt might show `...\mobile>` or `.../mobile $`).

---

### Step 4: Install the app’s dependencies (one time only)

- **Where to type:** Same terminal, same folder (you must be in the `mobile` folder).
- Type exactly: `npm install`
- Press Enter. Wait until it finishes. You only need to do this once per server.

---

### Step 5: Start the app

- **Where to type:** Same terminal, still in the `mobile` folder.
- Type exactly: `npm start`
- Press Enter. A **browser window** will open on the Linux server with a big **QR code**. Leave that window open. Leave the terminal open too.

---

### Step 6: Open the app on your phone

- **Your phone and the Linux server must be on the same Wi‑Fi.**

- **iPhone:** Unlock your phone. Open the **Camera** app. Point the camera at the **QR code on the Linux server screen**. A small banner or notification will appear at the top. Tap it. It will open the app in **Expo Go**. The Rankings Bot app should load.
- **Android:** Unlock your phone. Open the **Expo Go** app. Tap **“Scan QR code.”** Point the camera at the **QR code on the Linux server screen**. The Rankings Bot app should load.

---

### Step 7: Log in

- On the phone you’ll see a login screen. Use the **same username and password** as the website.
  - Example: username `user`, password `user123`.
- Tap **Sign In**. If you see **“Network error”**, go to Part 2 below.

---

### Step 8: Use the app

- Tap **Rankings** to see the list. Switch between **WPBA** and **WPA** at the top.
- Tap **Settings** to see the log-out button.

---

## Part 2: If you get “Network error”

- [ ] **Same Wi‑Fi:** Your phone and the server (where you ran `npm start`) must be on the same Wi‑Fi. Check the Wi‑Fi name on both.

- [ ] **Point the app at this server:** On the server, get its IP (e.g. `hostname -I` or `ip addr`). In the terminal on the server, in the `mobile` folder, before `npm start`, run: `export EXPO_PUBLIC_API_URL=http://SERVER_IP:8003` (use the server IP). Then run `npm start` again and scan the QR code again.

---

## Part 3: Build a real app file (when you’re ready)

This creates a file you can install on your phone (no Expo Go needed): `.apk` for Android, `.ipa` for iPhone.

- [ ] **Create an Expo account**  

- [ ] **Install EAS CLI on the Linux server** (one time)  
  **Where to type:** Terminal on the server. Type: `npm install -g eas-cli` then Enter. **Installs to:** The server (global npm). Then `eas login` (Expo account).
  You are now logged in on the server.

- [ ] **Configure the project** (one time)  
  **Where to type:** In the terminal, go to the `mobile` folder first (same as Step 3 in Part 1: `cd` to `rankings-bot/mobile`). Then type: `eas build:configure` and Enter. It will ask some questions — accept the defaults (press Enter). It creates a file `eas.json` inside `mobile/`.

- [ ] **Build for Android** (easiest)  
  **Where to type:** Terminal, in the `mobile` folder. Type: `eas build --platform android --profile preview` and Enter. The build runs on Expo’s servers (not the Linux server). When it’s done, the terminal will show a **link**.  
  **From:** That link (open it in the Linux server’s browser or on your phone). **To:** Download the `.apk` file. **Install on phone:** Copy the APK to your Android phone (email, USB, or download on the phone from the same link). Open the APK on the phone — you may need to allow “Install from unknown sources” in Settings.

- [ ] **Build for iPhone** (needs Apple)  
  You need a paid **Apple Developer** account ($99/year) at https://developer.apple.com. Then in the terminal (in `mobile` folder) type: `eas build --platform ios --profile preview` and Enter. Follow the prompts to sign in with Apple. When done, you get a link to download the `.ipa` or install via TestFlight.

---

## Part 4: Put the app in the stores (optional, later)

- [ ] **Apple App Store**  
  Need: Apple Developer account, app icons, screenshots, description, privacy policy. Build with EAS, then upload to App Store Connect and submit for review.

- [ ] **Google Play Store**  
  Need: Google Play Developer account (one-time fee), app icons, screenshots, description, privacy policy. Build with EAS (Android), upload the AAB to Play Console, and submit for review.

---

## Quick reference

| I want to…              | Do this                                      |
|-------------------------|----------------------------------------------|
| See the app on my phone | Part 1 (Expo Go + QR code)                   |
| Get an installable app  | Part 3 (EAS build)                           |
| Publish to App/Play Store | Part 4 (stores)                            |

---

## Where to get help

- **Expo docs:** https://docs.expo.dev  
- **Run/build issues:** Check the terminal and the error message; often it’s Node version, network, or missing login.  
- **Repo details:** See `mobile/README.md` and `docs/MOBILE_API.md`.
