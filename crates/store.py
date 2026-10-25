#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Build the AROS crate store: each crate pinned in crates.json, fetched from
crates.io (or a local Cargo cache), checked against its pinned SHA-256,
extracted and patched with its AROS diff. A consumer points its
[patch.crates-io] entries at OUTPUT/<name>-<version>.

    store.py --output DIR [--cargo-cache DIR] [--offline]
"""
import argparse, hashlib, io, json, pathlib, subprocess, sys, tarfile, urllib.request

HERE = pathlib.Path(__file__).resolve().parent


def crate_bytes(nv, pin, cache, offline):
    if cache:
        local = cache / f"{nv}.crate"
        if local.is_file():
            return local.read_bytes()
    if offline:
        raise SystemExit(f"{nv}: not in the Cargo cache and --offline was given")
    url = f"https://static.crates.io/crates/{pin['name']}/{nv}.crate"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output", type=pathlib.Path, required=True, help="new store directory")
    p.add_argument("--cargo-cache", type=pathlib.Path, help="a Cargo registry cache directory to read .crate files from")
    p.add_argument("--offline", action="store_true")
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit(f"{a.output} exists; give a new directory")
    pins = json.loads((HERE / "crates.json").read_text())
    a.output.mkdir(parents=True)
    for nv, pin in sorted(pins.items()):
        data = crate_bytes(nv, pin, a.cargo_cache, a.offline)
        digest = hashlib.sha256(data).hexdigest()
        if digest != pin["sha256"]:
            raise SystemExit(f"{nv}: sha256 {digest} does not match the pin {pin['sha256']}")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            archive.extractall(a.output, filter="data")
        diff = HERE / f"{nv}-aros.diff"
        subprocess.run(["patch", "-s", "-p1", "--no-backup-if-mismatch", "-i", str(diff)],
                       cwd=a.output / nv, check=True)
        print(f"{nv}: patched")
    print(f"store: {a.output}")


if __name__ == "__main__":
    sys.exit(main())
