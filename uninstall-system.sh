#!/bin/sh
set -eu
task_root="/Library/Application Support/CodexPrewarm"
/bin/launchctl bootout system/local.codex-prewarm.wakes 2>/dev/null || true
if [ -f "$task_root/wake.py" ]; then
  /usr/bin/python3 -I "$task_root/wake.py" --cancel
fi
/bin/rm -f /Library/LaunchDaemons/local.codex-prewarm.wakes.plist
