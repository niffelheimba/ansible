#!/usr/bin/env python3
"""Offline policy validation against the installed, pinned upstream role."""
import argparse
from pathlib import Path
import re
import yaml

REPO = Path(__file__).resolve().parents[1]
REVISION = '3a2f05b9a8040eb869fd14fdca882aae4f68733b'
TASK_FILES = {
    'section_1/cis_1.5.x.yml', 'section_1/cis_1.6.x.yml',
    'section_2/cis_2.4.1.x.yml', 'section_5/cis_5.1.x.yml',
    'section_6/cis_6.2.1.x.yml', 'section_7/cis_7.1.x.yml',
}
ALLOWED = {
    '1_5_1', '1_6_2', '1_6_3', '1_6_5', '1_6_6',
    '2_4_1_2', '2_4_1_3', '2_4_1_4', '2_4_1_5', '2_4_1_6', '2_4_1_7',
    '5_1_1', '5_1_2', '5_1_3', '6_2_1_1', '6_2_1_2',
    '7_1_1', '7_1_2', '7_1_3', '7_1_4', '7_1_9',
}


def validate(role):
    config = yaml.safe_load((REPO / 'vars/ubuntu24-cis-northlake.yml').read_text())
    requirements = yaml.safe_load((REPO / 'roles/requirements.yml').read_text())
    assert requirements['roles'][0]['version'] == REVISION, 'Upstream revision changed'
    installed = yaml.safe_load((role / 'meta/.galaxy_install_info').read_text())
    assert installed['version'] == REVISION, 'Installed role does not match the pinned revision'
    play = yaml.safe_load((REPO / 'harden-ubuntu24-northlake.yml').read_text())[0]
    imports = [t['ansible.builtin.import_role'] for t in play['tasks']]
    assert {t['tasks_from'] for t in imports} == TASK_FILES, 'Task entrypoints changed'
    assert all(t['name'] == 'ubuntu24_cis' for t in imports)
    assert play['serial'] == 1 and play['any_errors_fatal'] is True
    assert 'oracle_cloud' in play['hosts'], 'Unexpected default target'
    referenced = set()
    for relative in TASK_FILES:
        text = (role / 'tasks' / relative).read_text()
        referenced.update(re.findall(r'ubtu24cis_rule_[0-9_]+', text))
        # Nothing in these task files may run without a rule condition.
        for task in yaml.safe_load(text):
            assert 'ubtu24cis_rule_' in str(task.get('when', '')), task['name']
    configured = {k for k in config if k.startswith('ubtu24cis_rule_')}
    assert referenced == configured, f'Unaccounted rule flags: {referenced ^ configured}'
    assert all(type(config[k]) is bool for k in configured)
    enabled = {k.removeprefix('ubtu24cis_rule_') for k in configured if config[k]}
    assert enabled == ALLOWED, f'Allowlist changed: {enabled ^ ALLOWED}'
    for section in range(1, 8):
        assert config[f'ubtu24cis_section{section}'] is False
    for flag in ['run_audit', 'setup_audit', 'audit_only', 'create_benchmark_facts',
                 'update_audit_template', 'ubtu24cis_disruption_high',
                 'ubtu24cis_disable_dynamic_motd']:
        assert config[flag] is False, flag
    assert config['skip_reboot'] is True
    assert config['ubtu24cis_sysctl_kernel_conf'] == '/etc/sysctl.d/99-northlake-aslr.conf'
    print(f'PASS: {len(referenced)} explicitly configured rule flags; '
          f'{len(enabled)} selected controls in six pinned entrypoints')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role_directory', type=Path)
    validate(parser.parse_args().role_directory)
