#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Assemble the patched AWS-LC XTS routines and verify their ELF function types."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--crate', required=True, type=Path)
p.add_argument('--clang', required=True, type=Path)
p.add_argument('--readelf', required=True, type=Path)
a = p.parse_args()
crate = a.crate.resolve()
rows = []
with tempfile.TemporaryDirectory(prefix='aros-crypto-symbols-') as work:
    for suffix, name in [('enc', 'encrypt'), ('dec', 'decrypt')]:
        source = crate / ('aws-lc/third_party/s2n-bignum/s2n-bignum-to-be-imported/'
                          f'arm/aes/aes-xts-{suffix}.S')
        obj = Path(work) / (suffix + '.o')
        command = [str(a.clang.absolute()), '--target=aarch64-unknown-aros',
                   '-DBORINGSSL_PREFIX=aws_lc_0_45_0', '-DS2N_BN_HIDE_SYMBOLS']
        command += ['-I' + str(crate / rel) for rel in (
            'generated-include', 'aws-lc/include',
            'aws-lc/third_party/s2n-bignum/s2n-bignum-imported/include')]
        subprocess.run(command + ['-c', str(source), '-o', str(obj)], check=True)
        symbols = subprocess.check_output([str(a.readelf.absolute()), '-s', str(obj)], text=True)
        wanted = 'aws_lc_0_45_0_aes_hw_xts_' + name
        matches = [line.split() for line in symbols.splitlines() if line.split() and line.split()[-1] == wanted]
        if len(matches) != 1 or matches[0][3] != 'FUNC':
            raise SystemExit('missing ELF function identity: ' + wanted)
        rows.append(wanted)
print(json.dumps(dict(result='PASS', symbols=rows,
                     scope='AArch64 ELF assembly metadata; no cryptographic or OS runtime claim')))
