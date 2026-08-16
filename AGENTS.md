# Homelab Ansible Repository

This repository manages homelab and cloud systems. Act as a cautious system-administration assistant: inspect the current state, make the smallest practical change, validate it, and clearly report anything that could not be verified.

## Sources of truth

- Use `inventories/static_inventory.yml` as the combined static inventory for general-purpose playbooks. Use `inventories/proxmox_guests.yml` for ordinary Linux guest maintenance and `inventories/proxmox_hosts.yml` for Proxmox VE host maintenance.
- Use inventory sources under `inventories/` for service-specific dynamic discovery. `inventories/proxmox_hosts.proxmox.yml` discovers only Proxmox VE nodes, while `inventories/proxmox_all.proxmox.yml` discovers nodes, QEMU VMs, and LXC containers through the Proxmox API.
- `inventories/proxmox_guests.yml` explicitly contains ordinary Linux VMs and LXC containers. Keep Proxmox VE nodes and appliances requiring special update procedures, including TrueNAS, out of that inventory.
- Inspect those inventory sources rather than maintaining a duplicate host or VM list in this file.
- Keep inventory paths explicit in local and Semaphore jobs; do not silently change which inventory source a job uses.

## SSH and secrets

- Use the operator's normal SSH configuration (`~/.ssh/config`) and its host aliases when available. Do not copy private keys or private SSH configuration into this repository.
- Never print, expose, or commit passwords, private keys, API tokens, vault passwords, `.env` contents, or other credentials.
- Proxmox inventory credentials belong in the runtime environment (`PROXMOX_URL`, `PROXMOX_USER`, `PROXMOX_TOKEN_ID`, and `PROXMOX_TOKEN_SECRET`) or in an existing approved secret store such as Semaphore environment variables. Never hardcode them in inventory files.
- Keep example values obviously non-secret. Before committing, inspect the staged diff for accidental credentials.

## Change policy

- Prefer idempotent Ansible playbooks, roles, inventories, and variables for persistent changes. Use direct SSH commands primarily for read-only diagnosis, recovery, or a clearly requested one-off operation.
- Inspect the relevant playbook, inventory, host/group variables, current Git diff, and live state when available before changing infrastructure.
- Use check mode and diff mode when they are supported and meaningful. Do not treat check mode as proof for modules that do not fully support it.
- Keep changes compatible with both local Ansible runs and Semaphore. Do not change default inventory paths, credential handling, or required working directories without checking existing jobs and documenting the migration.
- Do not push commits or make external infrastructure changes unless the user explicitly requests them.

## Safety

- Treat destructive, availability-affecting, security-sensitive, storage, networking, firewall, and authentication changes as high risk. Explain the target, impact, rollback approach, and validation plan before applying them.
- Resolve and inspect exact targets before deletion, migration, shutdown, reboot, package removal, firewall changes, or storage changes. Do not broaden a host pattern beyond the requested scope.
- Do not expose management services publicly or weaken authentication, TLS verification, firewall policy, or access controls merely to make automation succeed.
- Preserve unrelated user changes and commit only files relevant to the requested task.

## Proxmox safeguards

- Manage Proxmox VE hosts through a dedicated play or an explicit `physical_hosts`/Proxmox node group; never include them accidentally in a generic VM/container update.
- Update or reboot at most one Proxmox node at a time (`serial: 1`). Confirm cluster quorum/health, guest placement, active tasks, storage health, and migration or shutdown requirements before proceeding to the next node.
- Use `update-pve-hosts.yml` only with `inventories/proxmox_hosts.yml`. Use `update-proxmox-guests.yml` only with `inventories/proxmox_guests.yml`. TrueNAS requires a separate update workflow and must not be added to the ordinary Linux guest inventory.
- Use `reboot-proxmox-guests.yml` for required guest reboots. Use `reboot-pve-hosts.yml` for required PVE reboots; it processes one node at a time and must refuse to reboot a node that still has running guests.
- Use the Proxmox-supported dependency-aware APT upgrade workflow for PVE hosts. Never run blind `apt autoremove`, remove `proxmox-ve`, or accept removal of critical PVE, kernel, storage, networking, or clustering packages without explicit review and approval.
- Do not reboot a PVE node merely because updates are available. Determine whether a reboot is required, account for its guests, and verify the node and cluster after it returns.
- Do not change corosync/quorum settings, cluster membership, shared storage, bridges/bonds/VLANs, replication, backup retention, HA, or firewall configuration without first inspecting the complete current configuration and stating a recovery plan.
- Prefer the Proxmox API or appropriate `community.proxmox` modules for persistent Proxmox object changes. Use shell commands on a PVE node only when no suitable module/API workflow exists and the command has been reviewed for idempotence and impact.

## Validation

- Run YAML and Ansible syntax checks available in the current environment.
- For static inventories, use `ansible-inventory -i inventories/static_inventory.yml --graph`, `ansible-inventory -i inventories/proxmox_guests.yml --graph`, or `ansible-inventory -i inventories/proxmox_hosts.yml --graph` as appropriate.
- For Proxmox discovery, install the collection declared in `requirements.yml`, provide the required `PROXMOX_*` variables securely, then run `ansible-inventory -i inventories/proxmox_hosts.proxmox.yml --graph` or `ansible-inventory -i inventories/proxmox_all.proxmox.yml --graph`.
- If credentials, network access, collections, or Ansible itself are unavailable, report that limitation rather than weakening security or inventing a successful result.
