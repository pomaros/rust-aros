#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Exercise actual core genmf/fetch ordering; network fetch is an explicit recorder."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--core', type=Path, required=True)
p.add_argument('--make', default='/opt/homebrew/bin/gmake')
p.add_argument('--output', type=Path)
p.add_argument('--libc-archive', type=Path, help='verified local crate for a real offline fetch/patch case')
a = p.parse_args()
results = []
with tempfile.TemporaryDirectory(prefix='core-libc-admission-') as tmp:
    root = Path(tmp)
    toolchain, crates = root/'core/tools/crosstools/rust/unmodified', root/'core/tools/crosstools/rust/crates'
    for component, target in [('toolchain', toolchain), ('application-libc', crates)]:
        subprocess.run([sys.executable, str(ROOT/'tools/export-core-toolchain.py'),
                        '--component', component, '--output', str(target)],
                       check=True, capture_output=True, text=True)
    # Tests may run before committing this guard; execute its actual working
    # source. After commit this copy is byte-identical to the exported helper.
    shutil.copyfile(ROOT/'toolchain/verify-application-libc.py', toolchain/'verify-application-libc.py')
    config = root/'core/config'; config.mkdir()
    (config/'make.tail').write_text('')
    shutil.copyfile(a.core/'tools/crosstools/rust.cfg', root/'core/tools/crosstools/rust.cfg')
    cache = root/'downloads/rust-crates'; cache.mkdir(parents=True)
    marker = root/'fetch-ran'
    fetch = root/'fetch.py'
    fetch.write_text('import json, sys\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text(json.dumps(sys.argv))\n')
    if a.libc_archive:
        pin = json.loads((ROOT/'crates/crates.json').read_text())['libc-0.2.190']['sha256']
        if hashlib.sha256(a.libc_archive.read_bytes()).hexdigest() != pin:
            raise ValueError('local libc archive checksum differs from canonical pin')
        shutil.copyfile(a.libc_archive, cache/'libc-0.2.190.crate')
    def configure(native, real=False):
        (config/'aros.cfg').write_text('\n'.join([
            'PYTHON := '+sys.executable,
            'TARGET_RUST_VER := '+('nightly-2026-08-04' if native else '1.98.1'),
            'AROS_TARGET_CPU := aarch64', 'AROS_TOOLCHAIN := llvm',
            'PORTSDIR := '+str(root/'ports'), 'PORTSSOURCEDIR := '+str(root/'downloads'),
            'GENDIR := '+str(root/'generated'),
            'CURDIR := tools/crosstools/rust/crates',
            'FETCH := '+(str(a.core.resolve()/'scripts/fetch.sh') if real else sys.executable+' '+str(fetch)), 'ECHO := echo', 'Q := @',
            'TEST := test', 'IF := if', 'TOUCH := touch', 'NOP := :'])+'\n')
    generated = root/'Makefile'
    subprocess.run([sys.executable, str(a.core/'tools/genmf/genmf.py'),
                    str(a.core/'config/make.tmpl'),
                    str(a.core/'tools/crosstools/rust/crates/mmakefile.src'), str(generated)], check=True)
    patch = crates/'libc-0.2.190-aros-native.diff'
    origin = crates/'NATIVE-LIBC-ORIGIN.json'
    patch_bytes, origin_bytes = patch.read_bytes(), origin.read_bytes()
    cases = ['valid', 'edited-patch', 'edited-origin', 'edited-both', 'missing-origin', 'symlink-patch', 'cached-crate-edited-patch', 'hosted-unaffected']
    if a.libc_archive: cases.append('real-offline-fetch')
    for case in cases:
        if patch.is_symlink(): patch.unlink()
        patch.write_bytes(patch_bytes); origin.write_bytes(origin_bytes)
        marker.unlink(missing_ok=True)
        configure(case != 'hosted-unaffected', case == 'real-offline-fetch')
        if case in ['edited-patch', 'edited-both', 'cached-crate-edited-patch']:
            patch.write_bytes(patch_bytes.replace(b'pub cond_clock: clockid_t,', b''))
        if case == 'edited-origin': origin.write_bytes(origin_bytes+b'\n')
        if case == 'edited-both':
            forged = json.loads(origin_bytes)
            entry = forged['files']['libc-0.2.190-aros-native.diff']
            entry['source_sha256'] = entry['export_sha256'] = hashlib.sha256(patch.read_bytes()).hexdigest()
            origin.write_text(json.dumps(forged)+'\n')
        if case in ['missing-origin', 'hosted-unaffected']: origin.unlink()
        if case == 'symlink-patch':
            copy = root/'elsewhere.diff'; copy.write_bytes(patch_bytes)
            patch.unlink(); patch.symlink_to(copy)
        if case == 'cached-crate-edited-patch':
            (cache/'.libc-0.2.190-fetched').touch()
        run = subprocess.run([a.make, '-j8', '-f', str(generated), 'SRCDIR='+str(root/'core'),
                              'rust-crates-libc'], cwd=root, capture_output=True, text=True, timeout=20)
        expected = case in ['valid', 'hosted-unaffected']
        passed = (run.returncode == 0) == expected and marker.exists() == expected
        if case == 'real-offline-fetch':
            destination = root/'ports'/('rust-crates-native-'+hashlib.sha256(patch_bytes).hexdigest())
            source = destination/'libc-0.2.190/src/unix/aros/mod.rs'
            passed = run.returncode == 0 and source.exists() and b'pub cond_clock: clockid_t,' in source.read_bytes()
        elif expected:
            arguments = json.loads(marker.read_text())
            destination = arguments[arguments.index('-d')+1]
            wanted = root/'ports'/('rust-crates' if case == 'hosted-unaffected' else
                                    'rust-crates-native-'+hashlib.sha256(patch_bytes).hexdigest())
            passed = passed and destination == str(wanted)

        row = {'case': case, 'result': 'PASS' if passed else 'FAIL', 'make_exit': run.returncode,
               'fetch_ran': marker.exists(), 'stdout': run.stdout, 'stderr': run.stderr}
        results.append(row)
        print(case+': '+row['result'], flush=True)
        if not passed: print(run.stdout+run.stderr)
if a.output: a.output.write_text(json.dumps(results, indent=2)+'\n')
raise SystemExit(0 if all(row['result']=='PASS' for row in results) else 1)
