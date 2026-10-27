# Northlake Ubuntu 24.04 hardening

`harden-ubuntu24-northlake.yml` applies a deliberately limited subset of
[Ansible Lockdown UBUNTU24-CIS](https://github.com/ansible-lockdown/UBUNTU24-CIS),
pinned to main revision `3a2f05b9a8040eb869fd14fdca882aae4f68733b` (1.8.0).
It is a first hardening stage, **not a full CIS Level 1/2 implementation or a
compliance certification**. No Ubuntu Pro subscription is required.

## Targets and impact

Default target: `oracle_cloud`, using `inventories/oracle_cloud.yml` explicitly.
Those two Oracle guests were verified as Ubuntu 24.04 on ARM64. The playbook is
architecture-independent and also supports x86-64 Ubuntu 24.04 guests. Other
Ubuntu releases, Debian, Proxmox VE and appliances must use other profiles.

One host is processed at a time. An error stops the rollout. Ubuntu 24.04 LXC
guests can receive the file controls, but skip ASLR and auditd because they share
the host kernel. No reboot, firewall, network, storage or authentication-policy
change is selected. Auditd installation can consume disk space and package
installation may run distribution service hooks; schedule a canary accordingly.

## Why these controls

Loki's Lynis events reviewed on 2026-10-26 contained these recurring suggestions
on all 10 audited hosts. Counts are distinct hosts reporting a finding over the
seven-day window, not a claim about a fresh scan after this change. Recommendations
also depend on host type and the installed Lynis version.

| Lynis finding | Northlake action | Selected CIS controls |
| --- | --- | --- |
| ACCT-9628: audit framework | Install auditd and audispd-plugins and enable auditd on VMs | 6.2.1.1–2 |
| BANN-7126 / BANN-7130: login notices | Manage `/etc/issue` and `/etc/issue.net` and their permissions | 1.6.2–3, 1.6.5–6 |
| FILE-7524: permissions | Root system cron directories/files when cron is installed; SSH config and host keys; passwd/group, backups and shells | 2.4.1.2–7, 5.1.1–3, 7.1.1–4, 7.1.9 |
| KRNL-6000: kernel tuning | Only ASLR (`kernel.randomize_va_space=2`), in a dedicated sysctl file, on VMs | 1.5.1 |
| AUTH-9230 / 9262 / 9282 / 9286 / 9328: password/PAM/aging/umask | Review Kanidm policy and local emergency accounts separately; no automated changes | Excluded |
| SSH-7408: multiple SSH suggestions | Only file permissions in this stage; authentication/forwarding suggestions remain for review | Partial scope only |
| LOGG-2154: remote logging; TOOL-5002: automation | Verify existing Alloy/Loki and Ansible/Semaphore coverage rather than installing duplicates | Excluded |
| PKGS-7370 / FINT-4350: package integrity / AIDE | Plan an integrity baseline after trusted packages/configuration are established | Deferred |

Creating `issue.net` does **not** activate SSH's `Banner` directive; that is left
unchanged along with all other SSH directives. Auditd starts with existing or
Ubuntu package-default logging settings. This profile does not add a complete
audit rule set, boot auditing, immutable rules, full-disk halt policies, or ship
audit logs to Loki. Verify retention and forwarding separately; process
accounting/sysstat are not substitutes for auditd and are not installed here.

The observed warnings about security repositories, firewall rules, pending
reboots, DNS and mail banners need host-specific follow-up. This profile will
not clear every Lynis finding, and score improvement is not the acceptance test.

## Docker, Compose and Kanidm exceptions

The profile avoids:

- Docker daemon edits/restarts; nftables/iptables/UFW changes; IP forwarding,
  bridge filters, reverse-path filtering or IPv6 tuning. VPN/router guests need
  routing and Compose uses Docker-managed networking.
- Disabling unprivileged user namespaces, changing subuid/subgid, disabling user
  services/lingering, changing umask or removing users/homes. These can interfere
  with rootless Docker and Kanidm-resolved users.
- Filesystem-wide chmod/chown, SUID cleanup, mount rewrites, `/tmp`/`/home` noexec,
  new partitions, boot/GRUB settings, kernel module removal, blanket AppArmor
  enforcement or systemd sandboxing of existing services. Compose volume UID/GID
  ownership and runtime access need workload-specific review.
- PAM/nsswitch/password quality/history/aging changes; sudo password requirements;
  SSH account allowlists, AuthorizedKeysCommand, UsePAM, authentication or
  forwarding changes. Ubuntu's shadow-file group ownership is preserved too.

Kanidm integration depends on [PAM/NSS](https://kanidm.github.io/kanidm/stable/integrations/pam_and_nsswitch.html)
and [SSH key lookup](https://kanidm.github.io/kanidm/stable/integrations/ssh_key_distribution.html).
Using Kanidm does not eliminate the need to protect local emergency accounts.
Its policy and those local accounts need a separate reviewed change. Docker's
[firewall integration](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
and [rootless requirements](https://docs.docker.com/engine/security/rootless/tips/)
also require exceptions to generic host recommendations.

## Configuration and dependency installation

Run from this repository on an Ansible control node (or WSL), with Ansible Core
2.19.x and Python 3.12 as validated. Dependencies are pinned separately from
the existing Proxmox collection. Install both role and collections:

```sh
ansible-galaxy role install --force -r roles/requirements.yml -p roles
ansible-galaxy collection install -r collections/requirements.yml -p collections
export ANSIBLE_COLLECTIONS_PATH="$PWD/collections"
python3 scripts/validate-northlake-hardening.py roles/ubuntu24_cis
ansible-playbook -i inventories/oracle_cloud.yml harden-ubuntu24-northlake.yml --syntax-check
ansible-playbook -i inventories/oracle_cloud.yml harden-ubuntu24-northlake.yml --list-hosts
```

`vars/ubuntu24-cis-northlake.yml` is the reviewed control list. The supported
runtime switches are `northlake_enable_auditd`, `northlake_enable_aslr`, and
`northlake_enable_banners` (all default true). Disable them with extra variables
where required. Do not override individual `ubtu24cis_rule_*` flags ad hoc: the
wrapper intentionally bypasses upstream `tasks/main.yml`, `prelim.yml` and whole
sections, so prerequisites for other controls are not present. All rules in the
six imported task files are explicitly enabled/disabled. The validator rejects
unaccounted flags or an expanded allowlist. Updating upstream requires reviewing
its tasks, handlers, templates and defaults, then rerunning validation.

The upstream role does not reliably support check mode. This wrapper explicitly
refuses `--check`; a passing syntax check is not proof of workload compatibility.
It performs no forced APT refresh, upgrades, autoremove or lock removal. Resolve
stale package locks or repositories separately if installation cannot proceed.

## Canary rollout and acceptance

Take a recoverable VM/boot-volume snapshot and have working console access.
Inspect exact targets first. Start with **one** Oracle VM during a maintenance
window, using the same SSH identity that should keep working afterward:

```sh
ansible-playbook -i inventories/oracle_cloud.yml harden-ubuntu24-northlake.yml \
  --limit cloud-vm-multi-02
```

The standalone inventory uses `ubuntu`. The Semaphore template **Ubuntu 24 CIS
Hardening - Northlake** uses the existing Oracle Cloud Ubuntu ARM64 inventory,
Github repository on `main`, and Oracle Cloud operations environment with
`ansible-service`. It defaults to `cloud-vm-multi-02`; the task limit can be
overridden for later reviewed runs. Automatic execution and parallel runs are
disabled; no schedule is configured. Adding the template does not execute it.
Semaphore discovers `roles/requirements.yml` and `collections/requirements.yml`
for dependency installation. Keep Galaxy installation enabled for this job.

The playbook checks the existing SSH config, records critical running system
services, backs up affected files on the guest, and checks protected configuration
contents afterward. It validates ASLR, auditd when selected, unchanged running
services, a fresh SSH connection, login-account resolution and working sudo.
Fingerprint checks cover the configured `/etc` paths and conventional rootless
Docker config locations under `/home/*` and `/root`. They do not follow symlink
targets or discover arbitrary user home/config directories. They detect changes;
they cannot guarantee that all applications remain functional.

Before proceeding to the second host, also verify:

1. A fresh Kanidm user SSH login and sudo, including an account other than the
   automation account; key lookup and identity resolution work.
2. As each rootless Docker owner, `docker info`, `docker ps`, and the relevant
   `docker compose ps`; compare with pre-run state. System service checks alone
   do not exercise user Docker services or container health.
3. Actual application requests, published ports, volume read/write access, and
   VPN connectivity. Keep an existing emergency session while testing.
4. Re-run `audit-lynis.yml` with the existing Loki environment. It targets
   `proxmox_guests`; the Oracle inventory contains that compatibility group, so
   use the same explicit inventory and `--limit`. Compare findings by test ID.
5. Repeat the hardening run on the canary to check convergence. Backup creation
   intentionally reports changed every run; selected controls should converge.

For other verified Ubuntu 24.04 guests, use the guest inventory, an explicit
single-host limit and `-e northlake_hardening_target_group=proxmox_guests`.
Ubuntu 22.04/Debian hosts will fail rather than be silently hardened.

## Backup and recovery

Each apply run saves a root-only `/var/backups/northlake-hardening/before-*`
directory on that host. `files.tar` contains affected files and metadata for
affected directories without recursively collecting cron/app data. It includes
SSH host keys; leave it private on the guest. `manifest.json` records originally
absent paths, modes/ownership, protected content fingerprints, prior ASLR,
audit package/service state and banner diversions. Backups are not fetched into
Git or sent to Loki. Retain/remove them through a deliberate retention policy.

On failure, the rollout stops; there is **no automatic rollback**. Use the
console/retained session. Review the manifest, then restore only affected files
and their owner/mode from the archive, remove newly created paths only when safe,
and undo only banner diversions added by this run (consult
`banner_diversions_before`; `dpkg-divert --remove --no-rename` removes a local
diversion without moving files). Do not blindly restore passwd/group over
subsequent account changes. Restore the previous ASLR file and runtime value
from the manifest if necessary. Auditd packages/service changes are not reversed
by extracting the archive; review the recorded prior state before changing them.
A VM snapshot is the fuller recovery path. Revalidate SSH/Kanidm, sudo, Docker
and applications before continuing.
