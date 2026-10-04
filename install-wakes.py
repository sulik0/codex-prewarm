#!/usr/bin/env python3
"""Stage outside Documents to avoid macOS privacy restrictions on root helpers."""
from pathlib import Path
import json
import shlex
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='codex-prewarm-install-', dir='/private/tmp') as folder:
    stage = Path(folder)
    for name in ('wake.py', 'local.codex-prewarm.wakes.plist', 'install-system.sh'):
        shutil.copyfile(source / name, stage / name)
    command = '/bin/sh ' + shlex.quote(str(stage / 'install-system.sh')) + ' ' + shlex.quote(str(stage))
    script = 'do shell script ' + json.dumps(command) + ' with administrator privileges'
    subprocess.run(['/usr/bin/osascript', '-e', script], check=True)
