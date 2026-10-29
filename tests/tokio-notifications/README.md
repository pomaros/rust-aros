# AROS Tokio notifications

The AROS Tokio signal driver subscribes to the reactor's existing Mio waker.
Its event flags and watch subscriptions retain Tokio's coalescing semantics;
notification needs no Unix-domain socket or second Mio waker. Each runtime
owns a distinct subscription, removed when its driver drops. Repeated
subscriptions to the same reactor have independent lifetimes.

This backend relies on AROS CRT callbacks executing synchronously in task
context. Its mutex-based wake fan-out must not be selected for operating
systems that deliver asynchronous POSIX handlers. It does not add Unix-domain
sockets, change unsupported socketpair errors or provide Unix process groups.

Run the host regression against explicitly selected patched sources:

```sh
python3 tests/tokio-notifications/host.py --tokio STORE/tokio-1.52.1 \
  --mio STORE/mio-1.2.1 --output NEW_DIRECTORY
```

It uses the actual AROS notification source with real host Mio reactors. Cases
cover wake-before-poll, multiple reactors, unsubscribe without removing another
subscription, concurrent notification, subscription churn and reuse after
coalesced wakeups. This establishes host synchronization behavior, not the
AROS task or signal ABI.

`native.rs` is a standalone application with Tokio features `rt-multi-thread`,
`time`, `net` and `signal`. Build it with the managed AROS SDK and selected crate
patches. In a disposable guest, require its runtime-construction, spawned-task,
timer and shutdown marker `TOKIO_NATIVE_NOTIFICATION_SIGNAL_PASS`, Shell
return zero and the normal strict desktop/capture/quiescence verdict.

The probe also registers a Tokio SIGUSR1 listener, calls the native CRT raise
function and requires the notification within a bounded timeout. AROS CRT
sigaction callbacks must provide valid siginfo; signal-hook-registry deliberately
aborts on null siginfo. This exercises synchronous callback delivery, not Unix
asynchronous signals or process groups. Application GUI and physical hardware
acceptance require their own evidence.
