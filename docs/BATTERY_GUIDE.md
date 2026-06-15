# Keeping SchoolApp Watcher alive on Xiaomi / Redmi (HyperOS / MIUI)

HyperOS aggressively stops background apps to save battery. The watcher is a
foreground service (with a persistent notification) and has a 15-minute
watchdog and a boot receiver, but HyperOS can still kill it unless you grant a
few permissions. Do these **once** after installing.

## Fastest path — the in-app onboarding
On first launch the app shows an onboarding screen with three buttons:
1. **Allow notifications** — grants `POST_NOTIFICATIONS` (Android 13+).
2. **Open battery settings** — set the app to **No restrictions**.
3. **Open auto-start settings** (Xiaomi only) — enable **Autostart**.

Tap each, follow the system screen, then **Done**. If a button doesn't open the
exact screen on your HyperOS version, use the manual steps below.

## Manual steps (backup)

### 1. Autostart
Settings → **Apps** → **Manage apps** → **SchoolApp Watcher** → enable **Autostart**.
(Or: Security app → **Permissions** → **Autostart** → toggle SchoolApp Watcher on.)

### 2. Battery: No restrictions
Settings → **Apps** → **SchoolApp Watcher** → **Battery saver** → choose
**No restrictions** (not "Battery saver").

### 3. Lock the app in Recents
Open **Recents** (the multitasking view) → swipe **down** on the SchoolApp
Watcher card → a **lock icon** appears. Locked apps are not killed when you
clear recents.

### 4. Notifications on
Settings → **Notifications** → **SchoolApp Watcher** → allow. Keep the
**"Watcher Status"** channel enabled (the persistent "Last check…" notification
is what keeps the service alive) and the **"Grade Updates"** channel for alerts.

### 5. (Optional) Disable MIUI optimization caveats
If checks still stop overnight, Settings → enable Developer options →
**Turn off MIUI optimization** is a heavy-handed last resort; usually steps 1–3
are enough.

## How recovery works (so you know it's covered)
- **App opened** → the watcher restarts immediately if it was enabled.
- **Service killed in the background** → the 15-minute **watchdog** restarts it
  when the heartbeat goes stale.
- **Phone rebooted** → the **boot receiver** restarts it (needs Autostart, step 1).

## Verifying it's running
Pull down the notification shade — you should see **"SchoolApp Watcher — Last
check: HH:MM"**. That timestamp updating over time means polling is working.
