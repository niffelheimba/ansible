#!/usr/bin/env python3
"""Test APT evidence semantics: completed upgrades, not installs or downloads."""
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'status', Path(__file__).with_name('host-maintenance-status.py'))
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class UpgradeEvidenceTests(unittest.TestCase):
    def test_install_and_incomplete_upgrade_do_not_count(self):
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'history.log'
            log.write_text('Start-Date: 2026-10-26  12:00:00\nInstall: lynis\n'
                           'End-Date: 2026-10-26  12:00:01\n\n'
                           'Start-Date: 2026-10-27  12:00:00\nUpgrade: openssl\n')
            self.assertIsNone(status.latest_upgrade([str(log)]))

    def test_rotated_logs_choose_latest_completed_upgrade(self):
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'history.log'
            old = Path(root) / 'history.log.1.gz'
            log.write_text('Start-Date: 2026-10-26  12:00:00\nUpgrade: openssl\n'
                           'End-Date: 2026-10-26  12:01:00\n')
            with gzip.open(old, 'wt') as out:
                out.write('Start-Date: 2026-08-26  12:00:00\nUpgrade: openssl\n'
                          'End-Date: 2026-08-26  12:01:00\n')
            expected = int(status.datetime(2026, 10, 26, 12, 1).timestamp() * 1000)
            self.assertEqual(status.latest_upgrade([str(old), str(log)]), expected)

    def test_missing_logs_stay_unknown(self):
        self.assertIsNone(status.latest_upgrade(['/nonexistent/history.log']))


if __name__ == '__main__':
    unittest.main()
