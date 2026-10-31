/* SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0 */
/*
 * MUTEX_INIT_AT(p, name), as CeeSafe ADR 0027 §3.1 proposes it for CosmoOS's kernel/include/kernel/mutex.h: a mutex in
 * static storage, left as mutex_init leaves one (kernel/scheduler/mutex.c:13, wait.c:16, spinlock.c:30); p is its
 * own address, an address constant. k3.py force-includes this until CosmoOS's header defines it.
 */
#ifndef MUTEX_INIT_AT
#define MUTEX_INIT_AT(p, n) { .lock = SPINLOCK_INIT(n), .owner = NULL, \
    .wq = { .lock = SPINLOCK_INIT(n), .waiters = LIST_HEAD_INIT((p)->wq.waiters), \
            .callbacks = LIST_HEAD_INIT((p)->wq.callbacks) }, \
    .name = (n), .class = 0, .pi_active = 0, .pi_link = LIST_HEAD_INIT((p)->pi_link), .handoff = NULL }
#endif
