#!/usr/bin/env python3
"""Inspect installed jobs and recorded outcomes; never send a model request."""
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
RUNTIME = Path.home() / 'Library/Application Support/CodexPrewarm'
ZONE = ZoneInfo('Asia/Shanghai')


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=25)
        return result.returncode == 0, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False, ''


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def history():
    records = []
    for name in ('prewarm.log.2', 'prewarm.log.1', 'prewarm.log'):
        path = RUNTIME / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            match = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ (\w+) (\{.*\})$', line)
            if match:
                try:
                    fields = json.loads(match[3])
                    fields.update(checked_at=dt.datetime.fromisoformat(match[1]).replace(tzinfo=ZONE).isoformat(),
                                  status=match[2])
                    records.append(fields)
                except (ValueError, TypeError):
                    continue
    return records


def main():
    import os
    user_loaded, user_text = command('/bin/launchctl', 'print', 'gui/' + str(os.getuid()) + '/local.codex-prewarm')
    root_loaded, root_text = command('/bin/launchctl', 'print', 'system/local.codex-prewarm.wakes')
    _, schedule = command('/usr/bin/pmset', '-g', 'sched')
    power_ok, power_text = command('/usr/bin/pmset', '-g', 'log')
    power_events = []
    wake_requests = []
    if power_ok:
        for line in power_text.splitlines():
            request_time = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) Wake Requests', line)
            if request_time:
                observed = dt.datetime.strptime(request_time[1], '%Y-%m-%d %H:%M:%S %z')
                for request in re.findall(r'\[[^\[\]]*local\.codex-prewarm\.[^\[\]]*\]', line):
                    wake_requests.append((observed, request_time[1] + ' ' + request))
            match = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) (Sleep|DarkWake|Wake)\s+(.*)$', line)
            if match and not (match[2] == 'Wake' and match[3].startswith('Requests')):
                power_events.append((dt.datetime.strptime(match[1], '%Y-%m-%d %H:%M:%S %z'), match[2], line))
    records = history()
    scheduled = [r for r in records if r.get('slot')]
    evidence = []
    for record in scheduled[-6:]:
        target = dt.datetime.fromisoformat(record['slot']).replace(tzinfo=ZONE)
        checked = dt.datetime.fromisoformat(record['checked_at'])
        wake_time = target - dt.timedelta(minutes=1)
        wakes = [p for p in power_events if p[1] == 'Wake' and abs((p[0] - wake_time).total_seconds()) <= 20]
        if not wakes or not (0 <= (checked - target).total_seconds() <= 1800):
            continue
        wake = wakes[-1]
        owner = 'local.codex-prewarm.' + wake_time.strftime('%Y%m%d-%H%M')
        own_requests = [r for r in wake_requests if r[0] <= wake[0] and owner in r[1]]
        sleeps = [p for p in power_events if p[1] == 'Sleep' and p[0] < wake[0]]
        next_sleeps = [p for p in power_events if p[1] == 'Sleep' and checked <= p[0] <= checked + dt.timedelta(minutes=10)]
        evidence.append({'slot': record['slot'], 'task_result': record,
                         'preceding_tagged_wake_request': own_requests[-1][1] if own_requests else None,
                         'preceding_sleep': sleeps[-1][2] if sleeps else None,
                         'wake_at_scheduled_time': wake[2],
                         'subsequent_sleep': next_sleeps[0][2] if next_sleeps else None,
                         'scope': 'observed sleep/wake and task execution; not proof of a new quota window'})
    config = read_json(RUNTIME / 'config.json') or {}
    confirmed = [r for r in records if r['status'] == 'new_window_verified']
    report = {
        'checked_at': dt.datetime.now(ZONE).isoformat(timespec='seconds'),
        'query_only_no_model_request': True,
        'model': config.get('model'), 'times': config.get('times'),
        'user_job_loaded': user_loaded, 'root_job_loaded': root_loaded,
        'user_job_last_exit_code': re.findall(r'last exit code = (\d+)', user_text),
        'root_job_last_exit_code': re.findall(r'last exit code = (\d+)', root_text),
        'remaining_tagged_wake_events': sum('local.codex-prewarm.' in line for line in schedule.splitlines()),
        'latest_observation': read_json(RUNTIME / 'status.json'),
        'latest_scheduled_result': scheduled[-1] if scheduled else None,
        'latest_verified_new_window': confirmed[-1] if confirmed else None,
        'sleep_wake_execution_evidence': evidence,
        'power_log_read_succeeded': power_ok,
        'wake_maintenance': read_json(Path('/Library/Application Support/CodexPrewarm/wake-status.json')),
    }
    output = BASE / 'healthcheck.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('checked_at', 'user_job_loaded', 'root_job_loaded',
                                            'remaining_tagged_wake_events', 'latest_verified_new_window')},
                     ensure_ascii=False))
    print('Sleep/wake executions found:', len(evidence))
    print('Report:', output)
    return 0 if user_loaded and root_loaded else 1


if __name__ == '__main__':
    raise SystemExit(main())
