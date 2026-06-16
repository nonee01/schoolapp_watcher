#!/usr/bin/env bash
# Install or upgrade the SchoolApp Watcher plasmoid.
set -euo pipefail

ID="com.notadil.schoolappwatcher"
PKG="$(cd "$(dirname "$0")" && pwd)/package"

if ! command -v kpackagetool6 >/dev/null 2>&1; then
    echo "error: kpackagetool6 not found — this needs KDE Plasma 6." >&2
    exit 1
fi

if kpackagetool6 --type Plasma/Applet --show "$ID" >/dev/null 2>&1; then
    echo "Upgrading $ID ..."
    kpackagetool6 --type Plasma/Applet --upgrade "$PKG"
else
    echo "Installing $ID ..."
    kpackagetool6 --type Plasma/Applet --install "$PKG"
fi

echo
echo "Done. Add it via: right-click panel -> Add Widgets -> \"SchoolApp Watcher\""
echo "Then open its settings and set the API URL + API key."
echo "If an existing copy doesn't refresh, restart Plasma:"
echo "  kquitapp6 plasmashell && setsid kstart plasmashell"
