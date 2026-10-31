# Async/await for CeeSafe — design proposal

Oct 31, 2026 · @Veeran Kutty · Revised the same day after a cross-check against the tree (see "Changes from the
first draft" at the end). The choices the implementation depends on are fixed in ADR 0031
(`spec/decisions/0031-async-await.md`), which takes precedence where the two differ: explicit scope allocators
(`scopeIn`), the shield deadline's `TimedOut`, console output from async code, and the built-in/library split.

## Summary

Recommendation: stackless, compiler-generated task frames that never move, run only inside structured scopes, and cancelled by request rather than by drop. Most of Rust's async pain comes from three choices CeeSafe does not have to copy: movable futures, detached `'static` tasks, and cancellation by dropping a suspended future.

The design rests on one invariant: **a task's frame is placed once and is never destroyed while it is suspended.** Everything else follows from it.

The key decisions:

1. **Stackless state machines, lowered to portable C.** An `async fn` becomes a frame struct and a `switch` on its resume state. No stack switching, so it works in C11, freestanding builds and the kernel.
2. **Frames don't move, so there is no `Pin`.** A started task is an owning handle to a frame at a fixed address. Borrows of locals across `await` need no special rules.
3. **Structured concurrency only.** Tasks are spawned into a scope that outlives them, so they can borrow from their parent. No `'static` bound, no `Arc<Mutex<…>>` by default.
4. **Cancellation is a request, observed at `await` points as an ordinary error.** Cleanup is normal code on the `?` path, so async cleanup needs no async drop.
5. **Effects catch the classic bugs at compile time.** A new `suspend` effect: blocking calls are rejected inside `async fn`, and spin guards cannot live across an `await`.
6. **One executor per thread; tasks don't migrate.** No `Send` requirement on tasks. Threads talk through `Send`-checked channels, a library type this work adds (ADR 0016 deferred channels; they do not exist yet).
7. **No hidden allocation.** Frame sizes are known at compile time; recursion and `dyn` dispatch allocate only through an explicit allocator.
8. **One standard executor, swappable.** The language fixes a tiny frame ABI; `std` ships one hosted executor and the kernel profile plugs in its own.

## What goes wrong in Rust and others

Ten failure modes recur in Rust async reports; each one below is something this design must rule out or make visible.

1. **`Pin` and self-referential futures.** A future holding a borrow of its own local cannot move, so Rust added `Pin`, `Unpin` and pin projection. It is the most cited source of confusion.
2. **Cancellation by drop.** Any future can be dropped at any `.await`, silently. In `select!` loops this loses data already read ("cancellation safety"), and there is no way to run async cleanup.
3. **No async drop.** Closing a socket or flushing a buffer needs I/O, but `Drop` is synchronous. Workarounds leak or block.
4. **`'static + Send` on spawn.** `tokio::spawn` tasks can outlive their spawner and move between threads, so everything becomes `Arc<Mutex<…>>` and owned clones.
5. **Blocking inside async.** A blocking call or a long computation stalls the whole executor thread. Nothing in the type system catches it.
6. **Holding a lock across `.await`.** A `MutexGuard` or `RefCell` borrow kept across a suspension deadlocks or makes the future `!Send`, reported far from the cause.
7. **Function colouring and runtime split.** Sync and async APIs are duplicated, and libraries bind to tokio or async-std, which don't interoperate.
8. **Hidden size and allocation.** Futures can be kilobytes; recursion needs `Box::pin`; `dyn` async traits box every call.
9. **Completion-based I/O is unsound to wrap.** With io\_uring or IOCP the kernel writes into a buffer after the future may have been dropped.
10. **Poor debuggability.** Stack traces show the executor, not the logical call chain; there is no task tree.

Other languages show the alternatives. Go and Java's virtual threads avoid colouring with stackful threads, at the cost of a runtime that switches stacks. Zig removed its colourless async in 0.11 because it could not be made to work well. Kotlin and Python's Trio show that structured concurrency with cooperative cancellation is workable in practice.

## What CeeSafe already has

CeeSafe starts in a better place than Rust did in 2019: six existing features remove whole problem classes before any async-specific design.

| Existing feature | Where | What it gives async |
| --- | --- | --- |
| Panic = abort, no unwinding | `spec/ownership.md` (OD-5) | A suspended frame is never unwound mid-flight; the only exits are `return` and abort |
| Context effects `sleep`, `alloc`; `@context(atomic)` types | `spec/type-system.md` §32 | The machinery for "no blocking in async" and "no spin guard across `await`" already exists |
| Fork-join scoped threads, `Thread.both` | §38.6, ADR 0018 | Precedent for children that borrow their parent; the loan rule must be extended for spawns (see Structured concurrency) |
| Closures borrow by default; capture conflicts are N0241 | §36.2 | Spawned task bodies get conflict checking once their loans are kept live for the scope |
| `Send` / `Share` | §38.1 | Cross-thread hand-off is already checked; tasks need not be |
| Explicit allocators, `Result<T, AllocError>`, stack placement of non-escaping boxes | §18, §30, placement pass (`src/backend/placement.cee`) | Frames can be placed without hidden heap use, and failures are values |

One more point matters: `async`, `await` and `yield` are already reserved keywords (`spec/language-spec.md` §1; `TokenKind.AsyncKeyword`, `AwaitKeyword`, `YieldKeyword` in `src/syntax/token.cee`), so the syntax costs no breaking change.

What CeeSafe does **not** have yet, and this work must add:

- **Channels.** ADR 0016 chose `Arc`/`Mutex`/atomics and left channels (and `Condvar`) as "a separate increment, each spec-first" (`spec/decisions/0016-m13-userland-threads.md`). No channel type exists in the spec or the library.
- **Non-blocking console, file and socket operations.** Every console, file, socket and process operation has the `sleep` effect (§32.1), so none of them can be called from an `async fn` as specified below.

## The proposed model

A program uses async through four things: `async fn`, `await`, `Async.scope` and `Async.run`. There is no user-visible `Future` trait, `poll` or `Pin` in the first version.

```ceesafe
async fn fetchBoth(net: borrow Net, a: StringView, b: StringView) -> Result<Pair, NetError> {
    var left = Buffer.withCapacity(4096)?;     // `Buffer` is illustrative: no such type in spec/api/core.md yet
    var right = Buffer.withCapacity(4096)?;
    await Async.scope(NetError.OutOfMemory, (s) => {
        s.spawn(async () => { await net.get(a, mut left)?; return Ok(); });   // borrows `left` from this frame
        s.spawn(async () => { await net.get(b, mut right)?; return Ok(); });  // a conflicting capture is N0241
    })?;                                                                         // returns only when both children have
    return Ok(Pair { left, right });
}

fn main() {
    let result = Async.run(fetchBoth(Net.system(), "a.example", "b.example"));
}
```

A closure body that uses `?` must have a result type that allows it (§36.2, N0261), so each child returns `Ok()`;
`spawn` supplies the expected type.

### Tasks and frames

- `async fn f(…) -> T` is a function whose call produces a task. In v1, a task must be awaited at once (`await f(x)`) or handed to `scope.spawn` / `Async.run`; anything else is a compile error. This removes the lazy-future footgun and first-class future combinators in one step.
- Each `async fn` gets a **frame**: a struct holding its arguments, the locals live across any `await`, its resume state and the frames of children it awaits directly. Its size and alignment are known at compile time.
- A frame is placed once and never moves. `await g()` places `g`'s frame inside the caller's frame; children awaited at different points share storage, as Rust's layout does. A spawned child's frame lives in the scope's storage, sized at compile time when the spawn count is fixed, or from the scope's allocator in a loop.
- Because frames don't move, a local may be borrowed across an `await` with no extra rule. The borrow checker treats `await` like a call that may run other tasks: nothing changes for code that does not share state.

### Structured concurrency

- `Async.scope(body)` runs `body`, which may `spawn` children. The scope returns only after every child has returned, like `Thread.both` but with any number of children.
- Children may capture anything their parent owns, by shared or mutable borrow. **This needs a new loan rule.** In `Thread.both`, N0241 between the two closures follows from both being arguments of one call (§38.6, "Loans"). Each `s.spawn(…)` is a separate call, so the spec must state that the loans of every closure passed to `spawn` stay live until the enclosing `Async.scope` returns. Then two children capturing the same value where either changes it is N0241, and nothing a child captures can be changed, moved or ended by the parent's `body` before the scope ends.
- **No `Send`/`Share` check on captures.** `Thread.both`'s capture rule (N0334) exists because one closure runs on another thread. Async children run on the scope's own thread, so that half of ADR 0018 does not apply.
- As in `Thread.both`, `spawn` accepts only a closure literal (or a function value), so its captures can be seen.
- The scope's result is the first error any child returned (others are cancelled; see below), or `Ok` when all succeed. `s.race(a, b)` and `s.all(…)` cover the common combinators.
- There is no detached `spawn` in v1. A later `Async.spawnOwned` can take a `move` literal whose captures are owned, never borrowed.

### Cancellation

- Cancelling a task **sets a flag; it never destroys a frame**. The frame is freed only after the task returns.
- The flag is observed only by **cancellable leaf operations**: I/O, timers, channel receives, `Async.checkpoint()`. On a cancelled task they return `Err(Cancelled)` at once, which every async I/O error type includes.
- User code propagates it with `?` like any other error, and destructors run in the normal order as the task returns. Cleanup that must itself do I/O goes in `Async.shield(…)`, where leaf operations ignore the flag (Trio's shield, bounded by a deadline).
- Consequences: cancellation can only happen at an `await` the reader can see; data already read is never lost silently; there is no need for async drop, because cleanup is ordinary code that may still `await` inside a shield.
- `drop` blocks and `defer` stay synchronous: an operation with the `suspend` effect inside them is N0295.

Task lifecycle (cancellation is a flag, not a drop):

```text
Created ──start──▶ Running ──await──▶ Suspended ──wake──▶ Running ──return──▶ Returned ──▶ Frame freed
                      ▲                    │
                      └──── cancel: flag set; the next leaf operation returns Err(Cancelled)
```

No arrow leads from Suspended to Frame freed: a cancelled task resumes, runs its cleanup on the `?` path, and returns like any other.

### Effects

- A new effect, **`suspend`**: the code may await. It is inferred like `sleep` and `alloc`. Today `@effects(…)` accepts only `sleep` and `alloc`, and any other name is N0290 (§32.2); the grammar, N0290's rule and the N0295 row in `spec/diagnostics.md` all change to admit `suspend`.
- **An `async fn` is a context that forbids `sleep`.** A blocking call such as `File.read` or `Mutex.lock` inside it is N0295, with the call chain in the message. The bridge is `await Async.blocking(() => …)`, which runs a closure on a worker thread (hosted profile only). That closure runs on another thread, so its captures follow `Thread.both`'s rule (§38.6): `Share` for shared use, `Send` for mutable use (N0334).
- **Console output is `sleep` today** (§32.1: console, file, socket and process operations all have `sleep`), so even `Console.writeLine` in an `async fn` is N0295. A1 must therefore ship non-blocking console and timer operations with the `suspend` effect, and A2 the file and socket ones; otherwise the first program cannot print.
- **Calls through closures.** A call through a function value or closure whose type has no effect list is taken to have `sleep` and `alloc` (§32.1, §36.3), so it is N0295 inside an `async fn`. `Async.scope`, `spawn`, `race`, `all` and `shield` are therefore `@effectsOf` their closure arguments (§32.5), and effect lists on closure types (§36.3) gain `suspend`, so an `async` closure parameter can be written `borrow @effects(suspend) fn(…)`.
- **`@context(atomic)` values forbid `suspend` while live.** A spin guard across `await` is a compile error, using the liveness rule §32.3 already defines.
- A blocking `std` `Mutex` cannot even be locked in an `async fn`, since `lock` has `sleep` (§38.3). `Async.Mutex` is the lock whose guard may be held across `await`.
- `@context(irq)` forbids `suspend` in addition to `sleep` and `alloc`: no awaiting in an interrupt handler.

### Threads and executors

- **One executor per thread; a task never moves between threads.** So tasks need not be `Send`, and the compiler never has to explain why a future is `!Send`.
- To use several cores, start several threads, each with `Async.run`, and connect them with channels whose payloads must be `Send` (N0334). Channels do not exist yet: A2 adds them as the library increment ADR 0016 deferred, spec first, over the existing `Arc`/`Mutex`/atomics.
- A later opt-in work-stealing executor can require frames to be `Send`. The compiler knows exactly which locals live across which `await`, so it can name the one local that blocks it.
- **The language fixes a small frame ABI**: a header with the resume function, state, parent and waker slot. `core` defines `Waker` and the I/O traits; `std` ships one hosted executor (epoll, kqueue, IOCP); the freestanding profile asks the environment for one. Libraries are written against `core` traits, so there is one ecosystem, not one per runtime.

### Colouring

- Colouring is accepted on purpose. An `await` marks every point where other tasks may run and cancellation may arrive; a systems language should show that.
- The bridges are `Async.run` (sync to async; it has `sleep`, so it cannot be called from async code) and `Async.blocking` (async to sync).
- Library functions that take closures can later be made suspend-polymorphic, the way `@effectsOf` already makes them effect-polymorphic: `forEach` with an async closure becomes an async `forEach` in that instantiation.

### Sizes and dispatch

- Recursion through `await` makes a frame infinitely large, so it is a compile error whose sure fix boxes the recursive call with an explicit allocator: `await Async.boxed(alloc, walk(child))?`.
- `--explain-frames` reports each async fn's frame size and the locals that make it large, as `--explain-allocations` does for boxes (`spec/optimisations.md`).
- Async methods in interfaces work with static dispatch at once. `dyn` dispatch of an async method comes later: the vtable carries the frame's layout, and the caller places it in a buffer or through an allocator it names.

### Completion-based I/O

- Since a suspended frame is never destroyed, a buffer lent to io\_uring or IOCP stays valid until the kernel is done with it. A cancelled read first cancels the kernel operation and waits for its completion, then returns `Err(Cancelled)`.
- This makes completion-based I/O sound with ordinary borrowed buffers, which Rust cannot offer.

### Debugging

- Scopes form a tree, and each frame's state maps to a source line. The runtime can print the task tree with the `await` each task is suspended at.
- The lldb and gdb scripts in `editors/debug/` (`ceesafe_lldb.py`, `ceesafe_gdb.py`) gain a `tasks` command that walks the same tree.

## Rust's problems, answered

Eight of the ten problems become compile errors or disappear by construction; colouring is kept on purpose, and debuggability improves but stays a tooling task.

| Rust problem | CeeSafe answer | Enforced by |
| --- | --- | --- |
| `Pin`, self-referential futures | Frames are placed once and never move; handles move | Construction: no API moves a frame |
| Cancellation by drop, lost data in `select!` | Cancellation is a flag seen at visible `await`s as `Err(Cancelled)`; frames freed only after return | Runtime invariant + `?` in the types |
| No async drop | Cleanup is code on the error path; `Async.shield` for cleanup that does I/O | `drop`/`defer` with `suspend` is N0295 |
| `'static + Send` on spawn, `Arc<Mutex>` everywhere | Scoped spawns borrow from the parent; one executor per thread | Borrow checker (new scope-loan rule, N0241), no `Send` bound |
| Blocking inside async | `async fn` forbids `sleep`; `Async.blocking` offloads | Effect checker, N0295 |
| Lock guard across `.await` | `@context(atomic)` guards forbid `suspend`; blocking mutexes can't be locked | Effect checker, N0295 |
| Colouring, tokio vs async-std | Colouring kept and bridged; one frame ABI and `core` I/O traits; one std executor | Language and library design |
| Hidden size and boxing | Sizes known; recursion needs an explicit allocator; `--explain-frames` | Compile error with a sure fix |
| Unsound completion I/O | Suspended frames are never freed, so lent buffers stay valid | Runtime invariant |
| Opaque traces | Task tree from scopes; `tasks` debugger command | Tooling |

## Where it goes in the compiler

Async is checked as ordinary code and transformed late: the coroutine split runs on NIR after every safety pass, so the borrow, move, drop and effect checkers need only small extensions.

1. **Syntax** (`src/syntax/`): `async fn`, `async` closure literals, prefix `await`. The keywords are already tokens (`src/syntax/token.cee`) that nothing else uses, so the parser only has to accept them. The formatter and AST printer follow.
2. **Checking** (`src/check/`): `await` only inside `async`; a task must be awaited or spawned; `suspend` as an effect name in `@effects` and in closure effect lists (`effects.cee`, which reads the attributes and effect lists); `@effectsOf` on the `Async` library functions; the scope-loan rule for `spawn` captures (`closures.cee`, with `threads.cee` for `Async.blocking`'s `Send`/`Share` check).
3. **NIR** (`src/nir/`): `await` is a terminator with a resume block, so borrow, move and drop analysis see it as a call. The existing passes run unchanged. The effect checker, `effect_check.cee` (after `drops.cee`, `src/nir/passes.cee`), infers `suspend` and adds the new contexts: `async` forbidding `sleep`, `atomic` and `irq` forbidding `suspend`, `drop`/`defer` forbidding `suspend`.
4. **A new pass, `coroutines.cee`**, after `drops.cee` and `effect_check.cee` and before the backend: liveness across each `await` decides which locals move into the frame; each `await` gets a state number; child frames awaited at different points share a union.
5. **Backend** (`src/backend/`): the frame becomes a C struct; the body becomes a resume function that opens with `switch (frame->state)` and jumps to labels. `#line` maps every state to source (`spec/c-backend.md` §`#line`). **The resume switch makes the graph irreducible** wherever an `await` sits inside a loop: its edge into the loop body is a retreating edge that is not a back edge, so `c_structurer.cee` falls back to flat C for that function (`spec/c-backend.md` §3). Recommended for v1: emit resume functions in flat form deliberately (the reference form, `--flat-c`), and treat a structurer that understands resume edges as a later readability improvement.
6. **Runtime** (`runtime/`): a small `ceesafe_rt_async.c` with the executor, timers and the I/O reactor, regenerated into `src/library/runtime.cee` by `tools/gen_runtime.py`; freestanding builds get only the frame ABI and expect the environment's executor.
7. **Interpreter** (`src/interpreter/`): frames as interpreter objects with a run queue. The interpreter stays the reference: corpus programs must print the same on both.
8. **Tooling**: `--explain-frames`, LSP hovers showing frame size, MCP and `explain` entries for the new diagnostics, a debugger `tasks` command.

The compiler itself does not use async, so the fixed point is unaffected until a later decision chooses to use it, for example in the language server.

## Phases and gates

Five phases, each closed by tests the contract suite already knows how to run; spec text comes first, per the project rule "spec before code".

1. **A0 — Decision and specification.** ADR 0031 (`spec/decisions/0031-async-await.md`) for the model, after Decision 0008 made `lib/` CeeSafe's; new sections in `spec/type-system.md` (§32 `suspend`, §36.3 effect lists, the scope-loan rule), `ownership.md`, `lifetimes.md`, `c-backend.md` (resume functions in flat form) and `diagnostics.md` (N0290, N0295 updated); diagnostic codes reserved. Gate: `tools/spec_check.py` clean, owner accepts the decision.
2. **A1 — Single task.** `async fn`, `await`, `Async.run`, timers, non-blocking console output, the `suspend` effect and its contexts, embedded frames, interpreter support. Gate: run-pass and check-fail corpus programs; C and interpreter agree; ASan, UBSan and leak checks clean.
3. **A2 — Scopes, cancellation and channels.** `Async.scope`, `spawn`, `race`, `all`, `shield`, `blocking`, `Async.Mutex`, sockets and files on epoll and kqueue. Channels as their own spec-first increment (ADR 0016), usable both between threads and between tasks. Gate: the cancellation sweep below; fault sweep (`tools/fault_sweep.py`) over frame allocation.
4. **A3 — Interfaces and sizes.** Async interface methods, boxed recursion with its fix, `--explain-frames`, the debugger `tasks` command. Gate: explain-report snapshots; `tools/debugger_check.py` extended.
5. **A4 — Platforms.** IOCP and io\_uring backends, the freestanding executor hook and a CosmoOS integration, optional `Send` work stealing, suspend-polymorphic closures. Gate: Windows and Linux runs; a CosmoOS boot test.

The acceptance tests, beyond ordinary corpus programs:

- **One check-fail program per Rust problem** in the table above, each expecting its diagnostic: blocking in async, spin guard across `await`, conflicting spawn captures, un-awaited task, async recursion, `await` in `drop`, and a call through a closure without an effect list inside an `async fn`.
- **A cancellation sweep**, modelled on `CEESAFE_FAIL_ALLOC_AT`: run each program once with `CEESAFE_CANCEL_AT=k` for every suspension point `k`, under ASan with leak checks. Every run must exit cleanly with no leak and no lost write.
- **A buffer-lifetime test** for completion I/O: cancel a read while the kernel holds the buffer, under ASan.
- **Determinism**: with a seeded scheduler, the same program prints the same output on C and the interpreter.

## Alternatives and open questions

Three other models were weighed; each fails one of CeeSafe's fixed requirements of portable C11, freestanding kernels, or no hidden runtime.

| Alternative | Why not |
| --- | --- |
| Stackful coroutines or green threads (Go, Java virtual threads) | No colouring, but needs stack switching in assembly per architecture, which C11 cannot express; stack sizes must be guessed; kernel stacks are small |
| Effect handlers (OCaml 5) | Same stack-switching requirement; a large new language feature |
| Rust's model: `poll`, `Pin`, cancel by drop, detached tasks | The source of the problems this design avoids |
| Zig's colourless async | Removed from Zig in 0.11 after it could not be made reliable |

Open questions for the owner:

1. **First-class tasks in v1?** Recommended: no. A task must be awaited or spawned at once; a `Task<T>` value type can come later if a real need appears.
2. **How `Cancelled` is typed.** Recommended: every async I/O error enum gains a `Cancelled` case, and `Async.checkpoint()` returns `Result<(), Cancelled>`. The alternative is a separate wrapper on every async result.
3. **What `race` does with a loser that also finished.** Recommended: `race` returns the winner and hands back any loser's completed value instead of dropping it.
4. **`await` and `?` precedence.** Recommended: prefix `await`, with `await f(x)?` meaning `(await f(x))?`, since a task itself is never a `Result`.
5. **Should a `defer` block be allowed to await inside an implicit shield?** Recommended: not in v1; keep `drop` and `defer` synchronous.
6. **Resume functions: flat or structured C?** Recommended: flat in v1 (see "Where it goes in the compiler", step 5).

## Changes from the first draft

A cross-check against the tree on 2026-10-31 corrected these points:

- **Channels do not exist.** The draft relied on "existing `Send`-checked channels". ADR 0016 deferred them (`spec/decisions/0016-m13-userland-threads.md`); A2 now adds them.
- **The ADR 0018 rule does not carry over as is.** N0241 between `Thread.both`'s closures comes from one call; separate `spawn` calls need an explicit scope-loan rule. `Thread.both`'s `Send`/`Share` capture check does not apply to same-thread children, but does apply to `Async.blocking`.
- **Console I/O has `sleep`** (§32.1), so non-blocking console output moves into A1.
- **Closures without an effect list count as `sleep` and `alloc`** (§32.1, §36.3); the `Async` functions are `@effectsOf`, and closure effect lists gain `suspend`.
- **`@effects` accepts only `sleep` and `alloc`** (§32.2, N0290); adding `suspend` changes that rule and the N0295 row in `spec/diagnostics.md`.
- **The effect checker is `src/nir/effect_check.cee`**, running after `drops.cee` (`src/nir/passes.cee`); `src/check/effects.cee` only reads the attributes.
- **The resume switch makes the control-flow graph irreducible** for an `await` inside a loop, so `c_structurer.cee` would fall back to flat C (`spec/c-backend.md` §3); flat resume functions are now the v1 plan.
- **`Thread.sleep` does not exist**; the example of a blocking call is now `Mutex.lock`.
- **The decision is ADR 0031** in `spec/decisions/`, where CeeSafe's language ADRs continue (Decision 0006 §2); Decision 0008 is the project decision that makes `lib/` CeeSafe's, which the library parts need.
- The example's child closures now return `Ok()`, as §36.2 requires for a body that uses `?`; `Buffer` is marked illustrative. The embedded lifecycle figure is replaced by a text diagram.
