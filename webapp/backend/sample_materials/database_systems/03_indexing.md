# Indexing and query acceleration

An index is an auxiliary data structure that lets the engine find rows without scanning the whole table. Balanced trees such as B plus trees keep keys sorted and support equality and range searches in logarithmic time. Hash indexes are faster for exact matches but cannot answer range predicates.

## Clustered and secondary indexes

A clustered index stores table rows in key order, so one clustered index usually exists per table. A secondary index stores the key with a pointer or row identifier to the base table. Secondary indexes accelerate filters on non primary columns but may require an extra lookup for each matching row.

## Selectivity and covering indexes

Selectivity measures how many rows an index removes from consideration, and highly selective columns make better index candidates. A covering index includes every column a query needs, so the engine answers from the index alone without touching the table. Indexing every column is harmful because each insert, update and delete must maintain every index.

## Reading an access plan

The query planner compares estimated costs of alternative access paths before choosing one. Statistics about value distribution guide those estimates, and stale statistics often cause poor plans. Students should practice reading an execution plan to see whether a query performs an index seek or a full table scan.
