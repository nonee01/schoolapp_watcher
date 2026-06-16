#!/usr/bin/env bash
# Remove the SchoolApp Watcher plasmoid.
set -euo pipefail
ID="com.notadil.schoolappwatcher"

if ! command -v kpackagetool6 >/dev/null 2>&1; then
    echo "error: kpackagetool6 not found — this needs KDE Plasma 6." >&2
    exit 1
fi

kpackagetool6 --type Plasma/Applet --remove "$ID"
echo "Removed $ID. Restart Plasma if it's still in a panel:"
echo "  kquitapp6 plasmashell && setsid kstart plasmashell"
