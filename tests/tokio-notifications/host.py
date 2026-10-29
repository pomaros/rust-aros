#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John Knipper
"""Exercise the actual patched AROS notification source with real host Mio reactors."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--tokio',type=Path,required=True);p.add_argument('--mio',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);out=a.output.resolve();src=out/'src';src.mkdir()
actual=a.tokio.resolve()/'src/runtime/signal/aros.rs';cases=Path(__file__).with_name('cases.rs').resolve()
(out/'Cargo.toml').write_text('[package]\nname="aros-notification-host"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nmio={path='+json.dumps(str(a.mio.resolve()))+',features=["os-poll"]}\n')
(src/'lib.rs').write_text('#[path='+json.dumps(str(actual))+'] mod notifications;\n#[cfg(test)] #[path='+json.dumps(str(cases))+'] mod cases;\n')
command=['cargo','test','--offline','--manifest-path',str(out/'Cargo.toml'),'--','--test-threads=1']
before=hashlib.sha256(actual.read_bytes()).hexdigest()
error=None
try:
 with (out/'test.log').open('w') as log:
  code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
except (OSError,subprocess.TimeoutExpired) as exc:
 code=1;error=str(exc)
if hashlib.sha256(actual.read_bytes()).hexdigest()!=before:
 code=1;error='source changed during test'
record={'result':'PASS' if code==0 else 'FAIL','scope':'host real Mio notifications; not AROS signal or task ABI acceptance','source_sha256':before,'command':command,'returncode':code,'error':error}
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(code)
