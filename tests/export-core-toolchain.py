#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Exercise real SDK export admission and refusal of edited source snapshots."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/export-core-toolchain.py'


class ExportAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rust-core-export-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'component'
        self.command('--output', self.output)

    def command(self, *arguments, success=True):
        result = subprocess.run([sys.executable, str(TOOL), *map(str, arguments)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_actual_snapshot_and_core_header_ownership(self):
        self.command('--check', self.output)
        self.assertFalse((self.output / 'include/bsdsocket/native.h').exists())
        self.assertTrue((self.output / 'sys/stack.c').is_file())
        self.assertTrue((self.output / 'poll-probe.rs').is_file())

    def test_edited_adapter_is_refused(self):
        adapter = self.output / 'net/socket.c'
        adapter.write_bytes(adapter.read_bytes() + b'\n/* unauthorized local edit */\n')
        result = self.command('--check', self.output, success=False)
        self.assertIn('export content differs: net/socket.c', result.stderr)

    def test_untracked_source_is_refused(self):
        (self.output / 'unreviewed.c').write_text('int unreviewed;\n')
        result = self.command('--check', self.output, success=False)
        self.assertIn('export inventory differs', result.stderr)

    def test_symlink_component_is_refused(self):
        link = self.root / 'alias'
        link.symlink_to(self.output, target_is_directory=True)
        result = self.command('--check', link, success=False)
        self.assertIn('component must be a real directory', result.stderr)

    def test_relative_output_outside_source_is_admitted(self):
        target = self.root / 'relative-component'
        relative = os.path.relpath(target, ROOT)
        result = subprocess.run([sys.executable, str(TOOL), '--output', relative],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.command('--check', target)

    def test_existing_output_is_preserved(self):
        manifest = (self.output / 'SOURCE-ORIGIN.json').read_bytes()
        self.command('--output', self.output, success=False)
        self.assertEqual((self.output / 'SOURCE-ORIGIN.json').read_bytes(), manifest)


class ApplicationLibcAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rust-libc-export-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'crates'
        self.command('--output', self.output)

    def command(self, *arguments, success=True):
        result = subprocess.run([sys.executable, str(TOOL), '--component',
                                 'application-libc', *map(str, arguments)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_exact_snapshot_and_shared_directory(self):
        expected = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                             'HEAD:crates/libc-0.2.190-aros.diff'])
        self.assertEqual((self.output / 'libc-0.2.190-aros-native.diff').read_bytes(), expected)
        (self.output / 'hosted-libc.diff').write_text('independently owned\n')
        self.command('--check', self.output)

    def test_edited_patch_is_refused(self):
        patch = self.output / 'libc-0.2.190-aros-native.diff'
        patch.write_bytes(patch.read_bytes().replace(b'pub cond_clock: clockid_t,', b''))
        result = self.command('--check', self.output, success=False)
        self.assertIn('export content differs', result.stderr)

    def test_missing_origin_is_refused(self):
        (self.output / 'NATIVE-LIBC-ORIGIN.json').unlink()
        self.command('--check', self.output, success=False)

    def test_symlink_patch_is_refused(self):
        patch = self.output / 'libc-0.2.190-aros-native.diff'
        moved = self.root / 'patch'; patch.rename(moved); patch.symlink_to(moved)
        self.command('--check', self.output, success=False)


if __name__ == '__main__':
    unittest.main()
