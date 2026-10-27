# Lynis audits

`audit-lynis.yml` installs the distribution's Lynis package if absent and runs
an unattended audit as root. It does not upgrade an installed Lynis package or
apply the hardening suggestions. It targets `proxmox_guests`, processes two
guests at a time, and supports Debian-family Linux systems. Proxmox nodes and
TrueNAS are outside this playbook's scope.

Run from this repository with an explicit inventory, starting with one guest:

```sh
ansible-playbook -i inventories/proxmox_guests.yml audit-lynis.yml --syntax-check
ansible-playbook -i inventories/proxmox_guests.yml audit-lynis.yml --check --limit home-vm-multi-01
ansible-playbook -i inventories/proxmox_guests.yml audit-lynis.yml --limit home-vm-multi-01
```

Check mode checks package requirements but skips the audit and artifact creation.
Each real run creates a private, unique dated directory under
`/var/log/lynis-audits` on each guest containing:

- `lynis-report.dat`: structured findings, including the hardening index.
- `lynis.log`: detailed audit log.
- `console.txt`: command output and exit status.
- `audit-events.jsonl`: JSON summary plus one event per warning/suggestion,
  ready for Loki ingestion. Summary fields include `scanned_at` (Unix seconds),
  `hardening_index` when available, `warnings`, `suggestions`, and `status`.
  Events carry `host`, `scan_id`, and `lynis_version`; findings also include
  `severity`, `test_id`, `message`, and `details`.

The same events appear as `LYNIS_EVENTS_B64=` records in the job output for
collection through the Semaphore API. A collector can decode these records and
push each host's JSON lines to Loki with labels `job="lynis"` and `host`.
Treat collection as one ingestion per task to avoid duplicate history.

Available partial results are collected before a nonzero exit status fails the
job. Findings alone do not fail the job. Each scan has a 30-minute timeout;
`lynis_audit_timeout` can override this. Results are retained without automatic
deletion; plan retention according to available disk space.

## Central collection and Semaphore

By default, copies are fetched into
`artifacts/lynis/<inventory-host>/<unique-run>/` on the **Ansible runner**.
This directory is ignored by Git. For a local run, the runner is the machine
executing Ansible; for Semaphore, it is the job's runner/container, not your PC.
Reports contain sensitive host details. Store them on a private, backed-up volume.

Semaphore checkouts and container filesystems may be temporary. For durable
central collection, mount a private persistent directory such as
`/var/lib/semaphore/reports` into the actual runner, ensure the runner user can
write there, and pass this extra variable:

```json
{"lynis_controller_root": "/var/lib/semaphore/reports/lynis"}
```

Use playbook `audit-lynis.yml`, repository `Github`, and an explicit guest inventory
in a new Semaphore Ansible template. The playbook must first be committed and
pushed to the repository branch used by Semaphore. No template, schedule, volume
mount, or live audit is created by adding these files.

Set `lynis_collect_reports: false` to keep only the copies on each guest.
Do not point collection at a public web directory or commit audit output.

## Grafana recommendation

Use persistent file storage as the archive of complete reports. Your
docker-compose repository already defines Loki and Alloy, so Loki is a suitable
next step for searchable findings, with Grafana providing the viewing layer.
An ingestion step could emit one JSON event per warning/suggestion and a summary
event per scan (host, scan time, Lynis version, hardening index, counts).
Keep host and job as stable labels; keep finding text and scan IDs in event data.
Do not treat the hardening index as a vulnerability count or proof of security.

This playbook generates events but does not itself push to Loki. The Grafana
dashboard `lynis-audits` uses the event schema above. A collector still needs to
ship events after each run (or Alloy can tail the persistent JSONL files).

References:
- https://cisofy.com/documentation/lynis/
- https://grafana.com/docs/loki/latest/visualize/grafana/
