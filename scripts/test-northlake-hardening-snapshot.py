#!/usr/bin/env python3
"""Offline tests: configuration contents, not intended chmods, trip the guard."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'snapshot', Path(__file__).with_name('northlake-hardening-snapshot.py'))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class FingerprintTests(unittest.TestCase):
    def test_content_changes_but_not_permissions_are_detected(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / 'sshd_config'
            config.write_text('AuthorizedKeysCommand /usr/sbin/kanidm_ssh_authorizedkeys %u\n')
            before = snapshot.fingerprint([root])
            config.chmod(0o600)
            self.assertEqual(before, snapshot.fingerprint([root]))
            config.write_text('AuthorizedKeysCommand none\n')
            self.assertNotEqual(before, snapshot.fingerprint([root]))

    def test_addition_deletion_and_absence_are_detected(self):
        with tempfile.TemporaryDirectory() as root:
            baseline = snapshot.fingerprint([root])
            config = Path(root) / 'new-config'
            config.write_text('test')
            self.assertNotEqual(baseline, snapshot.fingerprint([root]))
            config.unlink()
            self.assertEqual(baseline, snapshot.fingerprint([root]))
            missing = snapshot.fingerprint([str(config)])
            config.write_text('created')
            self.assertNotEqual(missing, snapshot.fingerprint([str(config)]))

    def test_symlink_target_content_is_not_followed(self):
        with tempfile.TemporaryDirectory() as root:
            link = Path(root) / 'link'
            link.symlink_to('/nonexistent-sensitive-path')
            self.assertEqual(snapshot.fingerprint([str(link)])[str(link)],
                             {'link': '/nonexistent-sensitive-path'})

    @unittest.skipUnless(hasattr(os, 'geteuid') and os.geteuid() == 0,
                         'Root-only snapshot test uses temporary files in Linux')
    def test_private_backup_and_verify_detect_tampering(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            config = base / 'config'
            config.write_text('original configuration')
            config.chmod(0o640)
            missing = base / 'missing'
            backups = base / 'backups'
            empty_result = subprocess.CompletedProcess([], 0, stdout='', stderr='')
            with patch.multiple(snapshot, BACKUP_ROOT=backups,
                                AFFECTED=[str(config), str(missing)],
                                AFFECTED_GLOBS=[], PROTECTED=[str(config)],
                                PROTECTED_GLOBS=[]), \
                    patch.object(snapshot.subprocess, 'run', return_value=empty_result), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                previous_umask = os.umask(0o077)
                try:
                    snapshot.snapshot()
                finally:
                    os.umask(previous_umask)
                backup = Path(json.loads(output.getvalue())['backup_dir'])
                manifest = json.loads((backup / 'manifest.json').read_text())
                self.assertEqual(manifest['affected'][str(config)]['mode'], 0o640)
                self.assertTrue(manifest['affected'][str(missing)]['absent'])
                self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
                self.assertEqual((backup / 'files.tar').stat().st_mode & 0o777, 0o600)
                with tarfile.open(backup / 'files.tar') as archive:
                    self.assertEqual(archive.extractfile(str(config).lstrip('/')).read(),
                                     b'original configuration')
                snapshot.verify(str(backup))
                config.write_text('unexpected change')
                with self.assertRaisesRegex(RuntimeError, 'Protected configuration changed'):
                    snapshot.verify(str(backup))


if __name__ == '__main__':
    unittest.main()
