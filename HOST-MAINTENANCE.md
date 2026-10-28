# Security dashboard: host maintenance

`collect-host-maintenance.yml` reads the ten ordinary Linux guests in
`inventories/proxmox_guests.yml` and publishes one JSON event per host to Loki
with labels `job=host_maintenance, host=<inventory name>`. No upgrades, package
cache refresh, reboot, hardening or persistent target configuration change is
performed by the collector. Ansible's temporary script files are removed normally.
Proxmox nodes, TrueNAS and guests absent from that inventory are outside this
table's coverage. Journald host aliases may differ from these inventory names.

Semaphore template **Collect Host Maintenance Status** uses the existing guest
inventory/SSH identity and a dedicated **Host maintenance telemetry** environment.
The environment supplies `host_maintenance_loki_url` and `ansible_user` through
Ansible extra variables. An hourly Semaphore schedule refreshes the readings.
The collector is safe to run manually; it fails after publishing an unknown row
for a host that cannot be read. Publishing errors also fail the task visibly.

The **Homelab Security** dashboard contains a maintenance table independent of
its journal-host filter. A separate Managed host filter covers the inventory
names. It shows the latest event for each host within a seven-day lookback ending
at the dashboard's selected end time. Last checked is displayed; a separate
staleness counter flags observations older than two hours. Refreshing the page
does not poll hosts; it reads Loki.
After seven days without collection a host's row disappears, so the collector
must remain healthy. Existing journal panels retain their original scope.

## What the columns mean

- **Operating system:** current `/etc/os-release` pretty name, including Ubuntu
  point release, plus architecture/runtime details.
- **Last successful update check:** per-host evidence of an upgrade task and
  subsequent package database check completing successfully. It can mean no
  packages were available. It is not a guarantee that every security fix is
  installed or that updates outside Ansible have been observed.
- **Last package upgrade:** newest completed `Upgrade:` transaction in retained
  APT history (including gzip rotations). Install-only activity, metadata
  downloads and incomplete transactions are excluded. Logs may have rotated
  away; missing evidence stays unknown. APT timestamps use host-local time.
- **Reboot required:** current Ubuntu `/run/reboot-required` flag, read during
  collection. Failed reads show Unknown, never No. Containers share a hypervisor
  kernel; an absent guest flag does not tell whether the Proxmox host needs a
  kernel reboot. The runtime column makes that limitation explicit.
- **Update age:** the last successful check and observation timestamps let you
  identify overdue hosts. Any age threshold is an operational reminder, not a
  compliance certification.
- **Last checked:** observation time, distinct from the update date. Red/amber
  reboot states and stale readings deserve investigation before remediation.

## Historical backfill and future reporting

`vars/maintenance-history.yml` contains a one-time backfill from Semaphore task
outputs 29 and 32. Only hosts with an explicit successful upgrade task and dpkg
consistency check are included. Task 32 failed overall, but six hosts have
verified success. Hosts with ignored SSH interruptions retain the older verified
date. Dry runs, Lynis audits and the Oracle preflight task do not count. Historical
timestamps use the task end time, so they are approximate per-host completion
times. The source column identifies the evidence.

Both guest update playbooks now import `tasks/record-successful-update.yml` only
at the end of successful real runs. They record a small root-owned marker at
`/var/lib/northlake-maintenance/last-successful-update.json`. Failed, skipped,
check-mode and ignored-unreachable upgrade results do not write a success marker.
The hourly collector prefers this marker over historical backfill when newer.
Manual Ansible runs also count as verified playbook update checks; the source
column identifies the playbook. Neither existing update template is run by
deploying this reporting change.

## Running locally and validation

```sh
ansible-playbook -i inventories/proxmox_guests.yml collect-host-maintenance.yml \
  -e host_maintenance_loki_url=http://your-private-loki:3100/loki/api/v1/push
python3 scripts/test-host-maintenance-status.py
ansible-playbook -i inventories/proxmox_guests.yml collect-host-maintenance.yml --syntax-check
```

The saved table, freshness counter, coverage note and variable definitions are in
`grafana/host-maintenance-panels.json`. The table merges Loki series, sorts by
observation time, and groups by inventory host before formatting date fields.
This ensures a newer failed reading replaces an older healthy one, instead of
showing stale success. The optional `scripts/test-maintenance-table.cjs` tests
these transformations with Grafana's own `@grafana/data` 13.2.4 library and rxjs
7.8.2; pass the directory containing those dependencies as its first argument.
Both actual ten-host readings and synthetic stale/unknown cases were validated.

The Loki destination belongs in Semaphore's environment, not a public endpoint.
No API tokens or private keys are stored in this repository. Existing approved
SSH credentials are reused. Future improvements include OS support-lifecycle
status, pending security-upgrade counts and an alert for a failed/stale collector.
Those require additional data/policy; this table does not fabricate them from
an OS version or an old successful update job.
