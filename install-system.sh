#!/bin/sh
set -eu
task_source="${1:?Pass the staging directory}"
task_root="/Library/Application Support/CodexPrewarm"
task_plist="/Library/LaunchDaemons/local.codex-prewarm.wakes.plist"
/usr/bin/install -d -o root -g wheel -m 755 "$task_root"
/usr/bin/install -o root -g wheel -m 644 "$task_source/wake.py" "$task_root/wake.py"
/usr/bin/install -o root -g wheel -m 644 "$task_source/local.codex-prewarm.wakes.plist" "$task_plist"
/usr/bin/plutil -lint "$task_plist"
/bin/launchctl bootout system/local.codex-prewarm.wakes 2>/dev/null || true
/bin/launchctl bootstrap system "$task_plist"
