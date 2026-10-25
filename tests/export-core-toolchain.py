#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Exercise real SDK export admission and refusal of edited source snapshots."""
from pathlib import Path
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

    def test_existing_output_is_preserved(self):
        manifest = (self.output / 'SOURCE-ORIGIN.json').read_bytes()
        self.command('--output', self.output, success=False)
        self.assertEqual((self.output / 'SOURCE-ORIGIN.json').read_bytes(), manifest)


if __name__ == '__main__':
    unittest.main()
