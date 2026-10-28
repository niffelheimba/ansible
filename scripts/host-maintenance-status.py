#!/usr/bin/env python3
"""Read host maintenance evidence; no package operations or persistent writes."""
import argparse
from datetime import datetime
import glob
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import time


def latest_upgrade(paths):
    latest = None
    for name in paths:
        opener = gzip.open if name.endswith('.gz') else open
        try:
            with opener(name, 'rt', errors='replace') as source:
                text = source.read()
            for entry in text.split('Start-Date:'):
                if not re.search(r'^Upgrade:', entry, re.M):
                    continue
                end = re.search(r'^End-Date:\s*(.+)$', entry, re.M)
                if end:
                    # APT logs contain host-local wall time without an offset.
                    local = datetime.strptime(' '.join(end[1].split()), '%Y-%m-%d %H:%M:%S')
                    stamp = int(local.timestamp() * 1000)
                    latest = max(latest or stamp, stamp)
        except (OSError, ValueError):
            continue
    return latest


def collect(host, history):
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            release[key] = value.strip('"')
    detected = subprocess.run(['systemd-detect-virt', '--container'],
                              capture_output=True, text=True)
    container = detected.returncode == 0
    ns = time.time_ns()
    event = {
        'event': 'host_status', 'host': host, 'observed_at_ms': ns // 1000000,
        'observed_at_ns': str(ns), 'collection_status': 'OK',
        'os': release.get('PRETTY_NAME', 'Unknown'),
        'os_id': release.get('ID', 'unknown'), 'version': release.get('VERSION_ID', 'Unknown'),
        'architecture': os.uname().machine, 'kernel': os.uname().release,
        'runtime': detected.stdout.strip() if container else 'VM / own kernel',
        'reboot_required': 'Yes' if Path('/run/reboot-required').exists() else
                           ('Shared kernel — no guest flag' if container else
                            ('No' if release.get('ID') == 'ubuntu' else 'No flag / OS dependent')),
        'last_package_upgrade_ms': latest_upgrade(glob.glob('/var/log/apt/history.log*')),
        'last_successful_update_ms': history.get('last_successful_update_ms'),
        'update_source': history.get('update_source', 'Unknown'),
        'update_task_id': history.get('update_task_id'),
    }
    marker = Path('/var/lib/northlake-maintenance/last-successful-update.json')
    if marker.exists():
        try:
            saved = json.loads(marker.read_text())
            if saved['completed_at_ms'] > (event['last_successful_update_ms'] or 0):
                event.update(last_successful_update_ms=saved['completed_at_ms'],
                             update_source='Verified playbook: ' + saved['playbook'],
                             update_task_id=None)
        except (OSError, ValueError, KeyError, TypeError):
            event['collection_status'] = 'Warning: invalid update marker'
    if event['last_successful_update_ms']:
        event['update_check_age_days'] = round(
            (event['observed_at_ms'] - event['last_successful_update_ms']) / 86400000, 1)
    else:
        event['update_check_age_days'] = None
    event['last_boot_ms'] = int((time.time() - float(Path('/proc/uptime').read_text().split()[0])) * 1000)
    return event


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--history-json', default='{}')
    args = parser.parse_args()
    print(json.dumps(collect(args.host, json.loads(args.history_json))))
