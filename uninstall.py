#!/usr/bin/env python3
"""Remove only this setup; retain source files and diagnostic logs."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parent
# Remove privileged wake events first. Cancellation of the auth dialog leaves
# the user scheduler intact, rather than half-removing the installation.
with tempfile.TemporaryDirectory(prefix='codex-prewarm-remove-', dir='/private/tmp') as folder:
    script_path = Path(folder) / 'uninstall-system.sh'
    shutil.copyfile(source / 'uninstall-system.sh', script_path)
    command = '/bin/sh ' + shlex.quote(str(script_path))
    script = 'do shell script ' + json.dumps(command) + ' with administrator privileges'
    subprocess.run(['/usr/bin/osascript', '-e', script], check=True)
domain = 'gui/' + str(os.getuid())
subprocess.run(['/bin/launchctl', 'bootout', domain + '/local.codex-prewarm'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
plist = Path.home() / 'Library/LaunchAgents/local.codex-prewarm.plist'
if plist.exists():
    plist.unlink()
print('Removed scheduled jobs and their tagged wake events. Diagnostic files retained.')
