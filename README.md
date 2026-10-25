# rust-aros

Rust for native AROS on AArch64, with the **official, unmodified Rust
compiler**: a target JSON, a library-only patch to the standard library,
native C adapters for networking and positioned I/O, and AROS patches for the
crates.io packages that need them. It is part of
[PomAROS](https://pomaros.com) and builds [Ferail](https://github.com/jonx/Ferail)
and [the Zed port](https://github.com/pomaros/zed) for AROS.

| Path | What |
|---|---|
| [`toolchain/`](toolchain/README.md) | the pinned official nightly (`channel.json`), the target (`aarch64-unknown-aros.json`), the std patch, the C adapters, `build.py` (builds std and a probe) and `integrate.py` (installs an SDK prefix with `rustc`, `cargo` and the AROS C linker driver) |
| `crates/` | one `<crate>-<version>-aros.diff` per patched crates.io package (two versions where consumers lock different ones), their pinned checksums (`crates.json`) and `store.py`, which builds the crate store |

## Building the SDK

Inputs: an AROS native C SDK (`Developer` directory of an AROS build), the
AROS cross C toolchain (`aros-crosstools`, clang and lld) and `collect-aros`.
Python 3.12 or newer; rustup is not needed.

```sh
python3 toolchain/integrate.py --prefix PREFIX --work WORK \
  --sdk AROS/Developer --crosstools aros-crosstools --collect-aros collect-aros \
  --host-triple aarch64-apple-darwin
python3 crates/store.py --output STORE
```

`PREFIX` then holds `bin/rustc`, `bin/cargo`, `bin/aarch64-aros-cc`, the target
and `aros-official-rust.json`, which records every input and output hash. An
application builds with Cargo through that prefix and points its
`[patch.crates-io]` entries for the patched crates at `STORE/<crate>-<version>`.

## Other architectures

The toolchain targets AArch64. [Adding an architecture](docs/adding-an-architecture.md)
lists what depends on the CPU and how to verify a new one.

## Hosted AROS

PomAROS Hosted runs AROS as a macOS process and reserves `x18` for the host;
its standard library is currently [jonx/rust-aros](https://github.com/jonx/rust-aros),
a port of std's platform layer for that target. Both serve the same goal (the
unmodified compiler with the platform in std) and are to become one.

## Runtime

Programs run on AROS systems, such as PomAROS VM, whose C runtime and network
stack provide the interfaces the adapters call (owned sockets through
bsdsocket vector 139, the POSIX descriptor dispatcher). Other AROS systems run
code that does not use them.

## Tests

```sh
python3 toolchain/net/tests/run.py --output OUT1
python3 toolchain/net/tests/socket/run.py --output OUT2
python3 toolchain/sys/test.py --output OUT3
```

run the adapters' host suites (fresh output directories).

## License

MIT for this project's files; the files derived from the AROS tree's Rust
port stay under the AROS Public License 1.1. [NOTICE](NOTICE) lists them.
