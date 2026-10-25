<!-- SPDX-License-Identifier: MIT -->
<!-- Copyright (c) 2026 John Knipper -->

# Adding an architecture

The toolchain targets `aarch64-unknown-aros` today. Most of it does not depend
on the CPU: the std patch selects AROS with `target_os = "aros"`, the crate
patches are written against the operating system, and the C adapters assume a
64-bit target that passes the library base last, not AArch64. What does
depend on the CPU is listed below, in the order to work through it.

## 1. What you need first

- **An AROS port for that CPU** that can run programs: its C SDK (the
  `Developer` directory of an AROS build for that CPU), the AROS cross C
  toolchain (`clang` and `lld` accepting `--target=<arch>-unknown-aros`) and
  `collect-aros`.
- **An LLVM backend for it in the pinned nightly.** The compiler is the
  official, unmodified one (`toolchain/channel.json`), so the CPU must be one
  its LLVM was built with. `rustc --print target-list` on that nightly shows
  targets for every backend it has.
- **A system to run on**, real or emulated, for the last step.

## 2. The target JSON

Add `toolchain/<arch>-unknown-aros.json` beside the AArch64 one. Copy the
fields that describe AROS unchanged (`os`, `target-family`, static
relocation, no PIC/PIE, no dynamic linking, `panic-strategy: abort`,
`has-thread-local: false`, the `gnu-cc` linker flavour, `-Wl,--no-gc-sections`,
`emit-debug-gdb-scripts: false`) and set the CPU fields:

| Field | Where it comes from |
|---|---|
| `arch`, `llvm-target`, `data-layout`, `target-pointer-width` | The pinned nightly, for the bare-metal target of that CPU: `rustc -Z unstable-options --print target-spec-json --target <arch>-unknown-none` (or `-none-elf`). The data layout must match that compiler's LLVM exactly. |
| `cpu`, `features`, `llvm-abiname` | The baseline the AROS C toolchain compiles that port for. |
| `code-model` | The code model of AROS user space on that CPU, as the AROS C toolchain uses it: `large` on AArch64 and x86_64, `medium` (medany) on riscv64. A mismatch produces relocations the AROS loader rejects. |
| `max-atomic-width` | What the CPU does atomically: 128 on AArch64, 64 on x86_64 and riscv64. |
| `stack-probes` | `inline` where LLVM supports it. |
| `linker` | `<arch>-aros-cc`, the driver `build.py` generates. |

The AROS project's own Rust port declares these targets in its compiler patch
(`compiler/rustc_target/src/spec/targets/*_unknown_aros.rs` in the AROS tree's
`tools/crosstools/rust/rustc-*-src-aros.diff`): use its values as the
reference for each CPU it supports.

## 3. The scripts

`build.py`, `integrate.py`, `consumer-check.py` and the two `ABI/` checks
spell the target as `aarch64-unknown-aros`: the target file name, the sysroot
path `lib/rustlib/<target>/lib`, `clang --target=…` for the adapters, the
generated `aarch64-aros-cc` driver and the `[target.…]` table of the installed
Cargo config. `build.py` also refuses a compiler whose `--print cfg` does not
include `target_arch="aarch64"`.

Make the target a parameter of these scripts (with `aarch64-unknown-aros` as
the default) rather than copying them per CPU, and derive the expected
`target_arch` from the target JSON.

## 4. The libc patch

`crates/libc-0.2.190-aros.diff`, and its copy in `toolchain/rust-src-aros.diff`
for std's vendored libc, must stay identical.

- **Gated blocks.** The `CMSG_*` helpers are under
  `cfg(all(target_os = "aros", target_arch = "aarch64"))` because they hard-code
  AROS's 16-byte alignment of ancillary data on AArch64. Check `AROS_ALIGN` for
  the new CPU in its `aros/<cpu>/cpu.h` and extend the condition or the
  constant.
- **Type widths.** x86_64 and riscv64 are LP64 like AArch64, so the AROS type
  definitions carry over. A 32-bit CPU (i386, ARM, m68k, PowerPC) needs every
  type and structure in the AROS module checked against that port's C headers
  (`c_long`, `off_t`, `time_t`, `blksize_t`, `pid_t`, and the socket and stat
  structures), field by field.

## 5. The C adapters

The adapters under `toolchain/net`, `fs` and `sys` call AROS libraries through
the SDK's library-call macros, so they follow the new CPU's calling convention
once they are compiled with its SDK. The network adapter converts the C
resolver's `addrinfo` from its LP64 layout to Rust's: a 32-bit CPU needs that
conversion revisited. The host tests (`toolchain/net/tests`,
`toolchain/sys/test.py`) mock the libraries and do not depend on the target.

## 6. The other crate patches

Search the patches for `target_arch` and `target_pointer_width`: most need
nothing, because they choose an AROS backend rather than a CPU one. Any
`cfg` that names `aarch64` gains the new CPU after its code has been checked
for it.

## 7. Verifying it

In this order, each step before the next:

1. `build.py --target …` compiles std and links its probe archive
   (`result.json`: compile and link `PASS`).
2. `integrate.py` installs an SDK prefix for that target, and
   `consumer-check.py` builds a Cargo consumer against the installed std.
3. `ABI/libc-exports.py` and `ABI/network-abi.py` match the libc declarations
   and the network structures against that CPU's SDK headers.
4. The host tests still pass.
5. On a running system of that CPU: the std probe (threads, files, sockets,
   environment, `available_parallelism()`), then a real program built with
   `crates/store.py`'s crate store.

Record the SDK, crosstools and compiler identities of that run with the
target, as `aros-official-rust.json` does for AArch64.
