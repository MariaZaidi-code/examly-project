# Storage structures and crash recovery

Databases store records in fixed size pages, and a buffer pool caches hot pages in memory. When a page is evicted, the manager writes it back to disk according to a replacement policy such as least recently used. A page identifier usually combines a file number with an offset.

## Write ahead logging

Write ahead logging requires the log record for a change to reach stable storage before the changed page is written. Each log entry carries a log sequence number, which recovery uses to decide whether a page change is durable. A checkpoint records that all pages before a certain point are safely on disk, which shortens recovery.

## ARIES style recovery

Recovery proceeds in three phases: analysis identifies active transactions and dirty pages, redo repeats history to restore committed work, and undo rolls back losers. Compensation log records make undo itself restartable after a second crash.

## Heap files and record layout

Heap files place records without ordering, so inserts are fast while scans may need indexes. Variable length records use slotted pages with offsets and length fields, which allow records to move within a page. Understanding pages, logs and checkpoints explains why committed data usually survives a crash while uncommitted work disappears.
