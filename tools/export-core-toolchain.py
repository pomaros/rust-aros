#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Export one immutable Rust SDK source revision for AROS core integration."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CORE_COMPONENT = 'tools/crosstools/rust/unmodified/'
NATIVE_HEADER = 'workbench/network/common/include/bsdsocket/native.h'
# The core owns this header. Its standalone snapshot is not a second provider.
EXCLUDED = {'include/bsdsocket/native.h'}
REWRITES = {
    'build.py': [('HERE / "include/bsdsocket/native.h"',
                  'HERE.parents[3] / "' + NATIVE_HEADER + '"')],
    'integrate.py': [("protected = [HERE.parent,", "protected = [HERE.parents[3],"),
                     ("HERE / 'include/bsdsocket/native.h'", "HERE.parents[3] / '" + NATIVE_HEADER + "'")],
    'ABI/network-abi.py': [('Path(__file__).resolve().parents[1] / "include/bsdsocket/native.h"',
                           'Path(__file__).resolve().parents[5] / "' + NATIVE_HEADER + '"')],
    'net/tests/socket/run.py': [("net.parent / 'include/bsdsocket/native.h'",
                                 "net.parent.parents[3] / '" + NATIVE_HEADER + "'")],
}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exported_files(revision):
    paths = git('ls-tree', '-r', '--name-only', revision, '--', 'toolchain/').decode().splitlines()
    files, provenance = {}, {}
    for path in paths:
        name = path.removeprefix('toolchain/')
        if name in EXCLUDED:
            continue
        original = git('show', revision + ':' + path)
        text = original.decode('utf-8')
        for old, new in REWRITES.get(name, []):
            if text.count(old) != 1:
                raise ValueError('integration rewrite preimage changed: ' + name + ': ' + old)
            text = text.replace(old, new)
        # These integration sources are John's code; preserve the core's APL
        # notices. Rust's library patch and third-party notices are untouched.
        if name.endswith(('.py', '.c', '.h', '.rs', '.md')):
            text = text.replace('SPDX-License-Identifier: MIT',
                                'Licensed under the AROS Public License (APL) Version 1.1')
        if name.endswith('.md'):
            text = text.replace('python3 toolchain/', 'python3 ' + CORE_COMPONENT)
        content = text.encode('utf-8')
        files[name] = content
        provenance[name] = {'source_sha256': digest(original), 'export_sha256': digest(content)}
    manifest = {'schema': 1, 'source_repository': 'https://github.com/pomaros/rust-aros.git',
                'source_revision': revision, 'source_directory': 'toolchain',
                'exporter_sha256': digest(Path(__file__).read_bytes()),
                'core_native_header': NATIVE_HEADER,
                'transformations': 'APL notices for owned integration files; authoritative core socket header paths; core command paths in documentation',
                'files': provenance}
    files['SOURCE-ORIGIN.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    return files


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision', default='HEAD', help='immutable SDK commit to export')
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--output', type=Path, help='new component directory; never overwrites a core tree')
    action.add_argument('--check', type=Path, help='verify an existing exported component without changing it')
    a = p.parse_args()
    try:
        revision = git('rev-parse', a.revision + '^{commit}').decode().strip()
        files = exported_files(revision)
        if a.check:
            target = a.check.resolve(strict=True)
            if target.is_symlink():
                raise ValueError('component must be a real directory')
            actual = {x.relative_to(target).as_posix() for x in target.rglob('*')
                      if x.is_file() or x.is_symlink()}
            if actual != files.keys():
                raise ValueError('export inventory differs: ' + str(sorted(actual ^ files.keys())[:12]))
            for name, content in files.items():
                path = target / name
                if path.is_symlink() or path.read_bytes() != content:
                    raise ValueError('export content differs: ' + name)
        else:
            target = a.output.absolute()
            if target.exists() or target.is_symlink():
                raise ValueError('output must not exist')
            if target == ROOT or ROOT in target.parents:
                raise ValueError('output must be outside the SDK source repository')
            target.mkdir(parents=True)
            for name, content in files.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                if name.endswith('.py'):
                    path.chmod(0o755)
        print(json.dumps({'result': 'PASS', 'mode': 'check' if a.check else 'export',
                          'source_revision': revision, 'files': len(files), 'component': str(target)}))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        p.exit(1, 'core-toolchain-export: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
