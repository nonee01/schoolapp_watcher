# SchoolApp Watcher — Mobile App (Android)

Expo/React Native app that talks to the Flask backend on the laptop.

## One-time setup

1. **Tailscale** (phone ⇄ laptop private network):
   - Laptop: `sudo pacman -S tailscale && sudo systemctl enable --now tailscaled && sudo tailscale up`
   - Phone: install Tailscale from Play Store, log in with the same account.
   - Get the laptop IP: `tailscale ip -4` (looks like `100.x.y.z`).

2. **Configure the app**: edit the two constants at the top of `App.tsx`:
   - `API_URL = 'http://<laptop-tailscale-ip>:8787'`
   - `API_KEY` = value of `API_KEY` in the project `.env`.

3. **Run it** (development, via Expo Go):
   ```bash
   cd mobile
   npm install
   npx expo start
   ```
   Install **Expo Go** on the phone, scan the QR code.

## Building the APK (local, no cloud)

Requires JDK 17 and the Android SDK (`/opt/android-sdk`, user-writable,
licenses accepted).

```bash
cd mobile
npx expo prebuild -p android   # generates the android/ native project
cd android
ORG_GRADLE_PROJECT_reactNativeArchitectures=arm64-v8a ./gradlew assembleRelease
```

APK lands at `android/app/build/outputs/apk/release/app-release.apk`.
Copy it to the phone (or `adb install`) and open it. The release build is
signed with the debug keystore — fine for personal use, but uninstall any
previous build signed differently before installing.

## Screens

- **Notes** — S4 modules with computed moyennes + validation badges
- **Absences** — sanctions banner + absence list (justified/not)
- **Résultats** — official semester results (moyenne, décision, classement) + official module decisions
- **Historique** — feed of every change the watcher detected
- **Statut** — watcher health, live countdown to the next check, force check now, pause/resume

The backend runs on the laptop as `schoolapp-api.service` (port 8787,
Flask + Waitress).
