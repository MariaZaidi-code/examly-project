# Database Systems: Transactions and Recovery (synthetic lecture notes)

## ACID properties
A transaction is a unit of work. ACID stands for atomicity, consistency, isolation and durability. Atomicity means all operations of a transaction happen or none do. Consistency means a transaction moves the database from one valid state to another. Isolation means concurrent transactions do not see each other's partial results. Durability means committed changes survive crashes.

## Recovery
Write-ahead logging records changes in a log before they reach the data pages, so after a crash the system can redo committed work and undo uncommitted work.

## Isolation levels
Read uncommitted allows dirty reads. Read committed prevents dirty reads. Repeatable read prevents non-repeatable reads. Serializable prevents phantom reads and makes concurrent execution equivalent to some serial order.
