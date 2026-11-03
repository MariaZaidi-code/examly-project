# Transactions and the ACID properties

A transaction is a unit of work that either completes entirely or leaves no effect. The database manager groups reads and writes so that concurrent users cannot observe half finished work. Applications mark boundaries with BEGIN, COMMIT and ROLLBACK statements.

## Atomicity and durability

Atomicity guarantees that a transaction is all or nothing, so a crash cannot leave a transfer with one account debited and the other untouched. Durability guarantees that committed changes survive a power failure, which is why the engine forces log records to stable storage before reporting success.

## Consistency and isolation

Consistency means each transaction moves the database from one valid state to another while respecting declared constraints. Isolation means concurrent transactions behave as if they executed one after another, although real systems relax this through isolation levels.

## Isolation levels and anomalies

Read uncommitted allows dirty reads of uncommitted data and is rarely appropriate for student records. Read committed prevents dirty reads but still allows non repeatable reads when another transaction updates a row. Repeatable read keeps rows stable but can allow phantom rows when new matches appear. Serializable prevents all three anomalies at the cost of more blocking or retries.

Transaction logs record before and after images, which the recovery manager uses to undo losers and redo winners after a failure.
