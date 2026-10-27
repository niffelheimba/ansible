# Oracle Cloud maintenance

Use `inventories/oracle_cloud.yml` explicitly for the two Oracle Cloud VMs.
It uses their public IPs from the operator's SSH configuration, preserves the
existing host names for audit history, and defaults to the `ubuntu` login.
Private keys are not stored in this repository.

The `oracle_cloud` group is the dedicated maintenance target. A legacy
`proxmox_guests` parent group allows existing guest audit playbooks to use this
inventory; it does not mean that these VMs run on Proxmox.

## Playbooks

- `validate-oracle-cloud.yml`: read-only SSH/sudo, Ubuntu ARM64, and package
  database checks. It installs no packages and does not refresh APT metadata.
- `update-oracle-cloud.yml`: performs those checks, refreshes APT metadata,
  installs available safe upgrades with package removals prohibited, then checks
  connectivity and the package database. It handles one VM at a time and stops
  on failure. It preserves local package configuration, does not remove packages,
  does not perform a distribution release upgrade, and does not reboot VMs.

Updates can restart services through package maintenance scripts. Use a
maintenance window and a tested backup or OCI boot-volume backup before applying
updates; package downgrades are not a dependable rollback strategy.

```sh
ansible-inventory -i inventories/oracle_cloud.yml --graph
ansible-playbook -i inventories/oracle_cloud.yml validate-oracle-cloud.yml
ansible-playbook -i inventories/oracle_cloud.yml update-oracle-cloud.yml --check --diff
ansible-playbook -i inventories/oracle_cloud.yml update-oracle-cloud.yml
```

Check mode does not prove that a real package upgrade will succeed. The reboot
flag shown in check mode reflects the current system, not a predicted result.

## Semaphore

The dedicated `Oracle Cloud Ubuntu ARM64` file inventory must point to
`inventories/oracle_cloud.yml` in repository `Github`. It uses the existing
Semaphore SSH key. The `Oracle Cloud operations` variable group overrides
`ansible_user` to `ansible-service`, matching that existing service credential;
local runs retain the default `ubuntu` login from the SSH configuration.
Use that variable group with templates using this inventory in Semaphore.

`Oracle Cloud Preflight` runs the read-only validation playbook. `Update Oracle
Cloud VMs` runs the update playbook. Neither template has a schedule.

The earlier audit found an APT metadata update on cloud-vm-multi-01 that had been
running for almost 57 days. These playbooks do not kill package processes or
delete lock files. If that operation is still holding the lock, an update job
can fail while refreshing metadata. Diagnose that condition separately before
applying updates; the read-only preflight does not prove APT locks are free.
