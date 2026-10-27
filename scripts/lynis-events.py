#!/usr/bin/env python3
"""Convert a Lynis report to JSON events without losing repeated findings."""
import argparse
import json
import time
from pathlib import Path


def convert(report, host, scan_id, exit_code):
    values = {}
    for line in report.splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values.setdefault(key, []).append(value)
    warnings = values.get('warning[]', [])
    suggestions = values.get('suggestion[]', [])
    common = {'host': host, 'scan_id': scan_id, 'scanned_at': int(time.time()),
              'lynis_version': values.get('lynis_version', ['unknown'])[-1]}
    summary = dict(common, event='summary', warnings=len(warnings),
                   suggestions=len(suggestions), exit_code=exit_code,
                   status='completed' if exit_code == 0 and values else 'failed')
    score = values.get('hardening_index', [''])[-1]
    if score.isdigit():
        summary['hardening_index'] = int(score)
    events = [summary]
    for kind, findings in [('warning', warnings), ('suggestion', suggestions)]:
        for finding in findings:
            parts = finding.split('|', 3)
            events.append(dict(common, event='finding', severity=kind,
                               test_id=parts[0], message=parts[1] if len(parts) > 1 else finding,
                               details='|'.join(parts[2:])))
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--scan-id', required=True)
    parser.add_argument('--exit-code', required=True, type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.report)
    events = convert(path.read_text(errors='replace') if path.exists() else '',
                     args.host, args.scan_id, args.exit_code)
    with open(args.output, 'w', encoding='utf-8') as output:
        for event in events:
            output.write(json.dumps(event) + '\n')
    Path(args.output).chmod(0o600)
    payload = {'streams': [{'stream': {'job': 'lynis', 'host': args.host},
                            'values': [[str(event['scanned_at'] * 1000000000 + index),
                                        json.dumps(event)]
                                       for index, event in enumerate(events)]}]}
    payload_path = Path(args.output).with_suffix('.loki.json')
    payload_path.write_text(json.dumps(payload), encoding='utf-8')
    payload_path.chmod(0o600)
    print(json.dumps(events))


if __name__ == '__main__':
    main()
