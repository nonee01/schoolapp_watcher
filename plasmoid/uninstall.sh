#!/usr/bin/env bash
# Remove the SchoolApp Watcher plasmoid.
set -euo pipefail
ID="com.notadil.schoolappwatcher"
kpackagetool6 --type Plasma/Applet --remove "$ID"
echo "Removed $ID. Restart Plasma if it's still in a panel:"
echo "  kquitapp6 plasmashell && setsid kstart plasmashell"
