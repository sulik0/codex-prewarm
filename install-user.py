#!/usr/bin/env python3
import os
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
HOME_PATH = Path.home()
RUNTIME = HOME_PATH / 'Library/Application Support/CodexPrewarm'
PLIST = HOME_PATH / 'Library/LaunchAgents/local.codex-prewarm.plist'
if not (SOURCE / 'config.json').exists():
    raise SystemExit('Run configure.py first to create the local account-bound config.')
config = json.loads((SOURCE / 'config.json').read_text())
intervals = []
for slot in config['times']:
    hour, minute = map(int, slot.split(':'))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise SystemExit('Invalid time in config.json')
    intervals.append({'Hour': hour, 'Minute': minute})
RUNTIME.mkdir(parents=True, exist_ok=True)
RUNTIME.chmod(0o700)
for name in ('prewarm.py', 'config.json'):
    shutil.copyfile(SOURCE / name, RUNTIME / name)
    (RUNTIME / name).chmod(0o600)
job = {
    'Label': 'local.codex-prewarm',
    'ProgramArguments': ['/usr/bin/caffeinate', '-is', sys.executable,
                         str(RUNTIME / 'prewarm.py'), '--scheduled'],
    'StartCalendarInterval': intervals,
    'EnvironmentVariables': {'HOME': str(HOME_PATH),
                            'PATH': config.get('child_path', '/opt/homebrew/opt/node@20/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'),
                            'TZ': config['timezone']},
    'WorkingDirectory': str(RUNTIME),
    'StandardOutPath': str(RUNTIME / 'launchd.log'),
    'StandardErrorPath': str(RUNTIME / 'launchd-error.log'),
    'ProcessType': 'Background',
    'ExitTimeOut': 20,
    'RunAtLoad': False
}
PLIST.parent.mkdir(parents=True, exist_ok=True)
PLIST.write_bytes(plistlib.dumps(job))
PLIST.chmod(0o644)
domain = 'gui/' + str(os.getuid())
subprocess.run(['/bin/launchctl', 'bootout', domain + '/local.codex-prewarm'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(['/bin/launchctl', 'bootstrap', domain, str(PLIST)], check=True)
print('Installed user agent:', PLIST)
print('Runtime:', RUNTIME)
