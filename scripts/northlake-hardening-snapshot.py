#!/usr/bin/env python3
"""Root-only, host-local recovery archive and content-preservation check.

Invoked by Ansible's script module. Never sends file contents to the controller.
Does not restore files automatically or attempt to reverse package installation.
"""
import glob
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile

BACKUP_ROOT = Path('/var/backups/northlake-hardening')
PROTECTED = [
    '/etc/pam.d', '/etc/nsswitch.conf', '/etc/sudoers', '/etc/sudoers.d',
    '/etc/subuid', '/etc/subgid', '/etc/kanidm', '/etc/docker',
    '/etc/ssh/sshd_config', '/etc/ssh/sshd_config.d',
    '/etc/passwd', '/etc/group', '/etc/shadow', '/etc/gshadow',
    '/etc/security', '/var/lib/systemd/linger',
    '/etc/systemd/system/docker.service.d',
    '/etc/systemd/system/user@.service.d',
]
PROTECTED_GLOBS = [
    '/home/*/.config/docker', '/home/*/.config/systemd/user',
    '/root/.config/docker', '/root/.config/systemd/user',
]
AFFECTED = [
    '/etc/issue', '/etc/issue.net', '/etc/passwd', '/etc/passwd-',
    '/etc/group', '/etc/group-', '/etc/shells', '/etc/crontab',
    '/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly',
    '/etc/cron.monthly', '/etc/cron.d',
    '/etc/sysctl.d/99-northlake-aslr.conf',
]
AFFECTED_GLOBS = [
    '/etc/ssh/sshd_config', '/etc/ssh/sshd_config.d/*.conf',
    '/etc/ssh/ssh_host_*_key', '/etc/ssh/ssh_host_*_key.pub',
]


def fingerprint(roots):
    """Hash contents and symlink destinations, not permitted metadata changes."""
    result = {}

    def visit(path):
        if path.is_symlink():
            result[str(path)] = {'link': os.readlink(path)}
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            result[str(path)] = {'sha256': digest.hexdigest()}
        elif path.is_dir():
            result[str(path)] = {'directory': True}
            for child in sorted(path.iterdir()):
                visit(child)
        elif not path.exists():
            result[str(path)] = {'absent': True}
        # Ignore sockets and other non-regular runtime files.

    for root in sorted(set(roots)):
        visit(Path(root))
    return result


def protected_roots():
    return PROTECTED + [p for pattern in PROTECTED_GLOBS for p in glob.glob(pattern)]


def snapshot():
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUP_ROOT.is_symlink() or BACKUP_ROOT.stat().st_uid != 0:
        raise RuntimeError('Backup root must be a real root-owned directory')
    BACKUP_ROOT.chmod(0o700)
    backup = Path(tempfile.mkdtemp(prefix='before-', dir=BACKUP_ROOT))
    paths = sorted(set(AFFECTED + [p for g in AFFECTED_GLOBS for p in glob.glob(g)]))
    metadata = {}
    with tarfile.open(backup / 'files.tar', 'w') as archive:
        for name in paths:
            path = Path(name)
            if path.is_symlink():
                raise RuntimeError(f'Review symlinked hardening target first: {name}')
            if path.exists():
                info = path.stat()
                metadata[name] = {
                    'uid': info.st_uid, 'gid': info.st_gid,
                    'mode': stat.S_IMODE(info.st_mode),
                }
                # Directory controls are not recursive; avoid archiving app data.
                archive.add(path, arcname=str(path).lstrip('/'), recursive=False)
            else:
                metadata[name] = {'absent': True}
    aslr = Path('/proc/sys/kernel/randomize_va_space')
    manifest = {
        'affected': metadata,
        'protected': fingerprint(protected_roots()),
        'aslr_before': aslr.read_text().strip() if aslr.exists() else None,
        'audit_packages_before': subprocess.run(
            ['dpkg-query', '-W', '-f=${binary:Package} ${db:Status-Abbrev}\n',
             'auditd', 'audispd-plugins'], capture_output=True, text=True).stdout,
        'audit_service_enabled_before': subprocess.run(
            ['systemctl', 'is-enabled', 'auditd.service'],
            capture_output=True, text=True).stdout.strip(),
        'audit_service_active_before': subprocess.run(
            ['systemctl', 'is-active', 'auditd.service'],
            capture_output=True, text=True).stdout.strip(),
        'banner_diversions_before': subprocess.run(
            ['dpkg-divert', '--list', '/etc/issue*'],
            capture_output=True, text=True).stdout,
    }
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'backup_dir': str(backup)}))


def verify(directory):
    backup = Path(directory).resolve(strict=True)
    if backup.parent != BACKUP_ROOT.resolve() or backup.stat().st_uid != 0:
        raise RuntimeError('Invalid backup directory')
    saved = json.loads((backup / 'manifest.json').read_text())['protected']
    current = fingerprint(protected_roots())
    changed = sorted(k for k in saved.keys() | current.keys() if saved.get(k) != current.get(k))
    if changed:
        # Names only, never configuration contents or credential material.
        raise RuntimeError('Protected configuration changed: ' + ', '.join(changed))
    print('Protected configuration contents unchanged')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root on the managed host')
    os.umask(0o077)
    if sys.argv[1:] == ['snapshot']:
        snapshot()
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify':
        verify(sys.argv[2])
    else:
        raise RuntimeError('Usage: snapshot | verify BACKUP_DIRECTORY')


if __name__ == '__main__':
    main()
