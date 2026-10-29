// SPDX-License-Identifier: MIT
// Copyright (c) 2026 John Knipper
fn main() {
    let rt = tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_all().build().unwrap();
    rt.block_on(async {
        let task = tokio::spawn(async { 42 });
        assert_eq!(task.await.unwrap(),42);
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    });
    drop(rt);
    println!("TOKIO_NATIVE_NOTIFICATION_RUNTIME_PASS");
}
