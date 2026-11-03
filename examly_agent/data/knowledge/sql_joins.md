# Database Systems: SQL Joins and Indexing (synthetic lecture notes)

## Joins
An inner join returns only rows with matching keys in both tables. A left outer join returns all rows from the left table and matching rows from the right, with NULL where there is no match. A full outer join returns unmatched rows from both sides. A cross join returns the Cartesian product.

## Join algorithms
Nested loop join compares every pair of rows and is simple but slow. Hash join builds a hash table on the smaller input and probes it with the other. Sort-merge join sorts both inputs on the join key and merges them.

## Indexes
Indexing structures such as balanced B-trees accelerate lookups on frequently queried attributes. A clustered index determines the physical order of rows; a table can have only one. Indexes speed up reads but slow down inserts and updates because they must be maintained.
