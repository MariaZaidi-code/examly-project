# Concurrency control and locking

Concurrency control lets many transactions run at the same time while preserving correctness. A shared lock permits several readers to hold the same resource, whereas an exclusive lock allows a single writer. Two phase locking requires a transaction to acquire all its locks before releasing any of them.

## Deadlock and starvation

A deadlock occurs when processes hold resources while waiting for resources held by other processes, so none can proceed. The engine detects cycles in the wait for graph and aborts one victim to break the cycle. Starvation happens when a transaction waits indefinitely because others keep overtaking it, which strict scheduling policies can prevent.

## Timestamps and optimistic control

Timestamp ordering assigns each transaction a timestamp and rejects operations that would violate serial order. Optimistic concurrency control validates read sets at commit time and restarts transactions that conflict. Multi version concurrency control keeps older versions so readers never block writers, which is popular in modern engines.

## Isolation in practice

Isolation levels trade consistency against throughput, and applications should choose the weakest level that remains correct. Long transactions increase contention and should be avoided in interactive study applications. Understanding locks, waits and versioning helps predict why a query blocks and how to fix it.
