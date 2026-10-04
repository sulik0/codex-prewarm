#!/usr/bin/python3
"""Root-owned, bounded scheduler; only manages owner-tagged wake events."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/Library/Application Support/CodexPrewarm')
OWNER = 'local.codex-prewarm'
TIMES = [(8, 30), (14, 0), (19, 30)]


def main():
    if os.geteuid() != 0:
        raise SystemExit('Administrator authorization required')
    cancel = '--cancel' in sys.argv
    current = dt.datetime.now()
    existing = subprocess.check_output(['/usr/bin/pmset', '-g', 'sched'], text=True)
    events, failures = [], []
    for offset in range(9):
        day = current + dt.timedelta(days=offset)
        for hour, minute in TIMES:
            target = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            wake = target - dt.timedelta(minutes=1)
            if not cancel and wake <= current:
                continue
            owner = OWNER + '.' + wake.strftime('%Y%m%d-%H%M')
            present = owner in existing
            if (not cancel and present) or (cancel and not present):
                continue
            command = ['/usr/bin/pmset', 'schedule']
            if cancel:
                command.append('cancel')
            command += ['wake', wake.strftime('%m/%d/%y %H:%M:%S'), owner]
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (events if result.returncode == 0 else failures).append(wake.isoformat())
    status = {'checked_at': current.astimezone().isoformat(), 'operation': 'cancel' if cancel else 'schedule',
              'changed_events': events, 'failed_events': failures, 'times': ['08:30', '14:00', '19:30']}
    (ROOT / 'wake-status.json').write_text(json.dumps(status, indent=2) + '\n')
    os.chmod(ROOT / 'wake-status.json', 0o644)
    print(json.dumps(status), flush=True)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
