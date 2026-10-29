// SPDX-License-Identifier: MIT
// Copyright (c) 2026 John Knipper
use crate::notifications::Notifications;
use std::{sync::Arc, time::Duration};
fn reactor() -> (mio::Poll, Arc<mio::Waker>) {
    let poll = mio::Poll::new().unwrap();
    let wake = Arc::new(mio::Waker::new(poll.registry(), mio::Token(73)).unwrap());
    (poll, wake)
}
fn observed(poll: &mut mio::Poll) -> bool {
    let mut events = mio::Events::with_capacity(8);
    poll.poll(&mut events, Some(Duration::from_millis(20)))
        .unwrap();
    events.iter().any(|e| e.token() == mio::Token(73))
}
#[test]
fn pending_wake_multiple_reactors_and_unsubscribe() {
    let notifications = Box::leak(Box::new(Notifications::default()));
    let (mut first, wake1) = reactor();
    let (mut second, wake2) = reactor();
    let sub1 = notifications.subscribe(wake1.clone());
    let sub2 = notifications.subscribe(wake2.clone());
    notifications.notify();
    assert!(observed(&mut first));
    assert!(observed(&mut second));
    drop(sub1);
    assert_eq!(Arc::strong_count(&wake1), 1);
    notifications.notify();
    assert!(!observed(&mut first));
    assert!(observed(&mut second));
    drop(sub2);
    assert_eq!(Arc::strong_count(&wake2), 1);
}
#[test]
fn concurrent_notification_and_subscription_lifetime() {
    let notifications: &'static Notifications = Box::leak(Box::new(Notifications::default()));
    let (mut poll, wake) = reactor();
    let subscription = notifications.subscribe(wake.clone());
    std::thread::scope(|scope| {
        for _ in 0..4 {
            scope.spawn(move || {
                for _ in 0..1000 {
                    notifications.notify();
                }
            });
        }
        scope.spawn(|| {
            for _ in 0..1000 {
                drop(notifications.subscribe(wake.clone()));
            }
        });
    });
    assert!(observed(&mut poll));
    notifications.notify();
    assert!(observed(&mut poll));
    drop(subscription);
    assert_eq!(Arc::strong_count(&wake), 1);
}
