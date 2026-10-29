// SPDX-License-Identifier: MIT
// Copyright (c) 2026 John Knipper
unsafe extern "C" {
    fn raise(signal: i32) -> i32;
}
fn main() {
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let task = tokio::spawn(async { 42 });
        assert_eq!(task.await.unwrap(), 42);
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        let kind = tokio::signal::unix::SignalKind::user_defined1();
        let mut listener = tokio::signal::unix::signal(kind).unwrap();
        assert_eq!(unsafe { raise(kind.as_raw_value()) }, 0);
        assert_eq!(
            tokio::time::timeout(std::time::Duration::from_secs(1), listener.recv())
                .await
                .unwrap(),
            Some(())
        );
    });
    drop(rt);
    println!("TOKIO_NATIVE_NOTIFICATION_SIGNAL_PASS");
}
