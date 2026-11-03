# Database Systems: Normalization (synthetic lecture notes)

## Why normalize
Normalization decomposes relations to reduce redundancy and avoid update, insertion and deletion anomalies.

## First normal form
First normal form (1NF) requires atomic attribute values: no repeating groups and no nested relations.

## Second normal form
Second normal form (2NF) removes partial dependencies. A relation is in 2NF if it is in 1NF and every non-key attribute depends on the whole candidate key, not on only part of a composite key.

## Third normal form
Third normal form (3NF) removes transitive dependencies so that non key attributes depend only on the primary key. If A determines B and B determines C, then C depends on A only through B. Example: Student(id, dept, dept_head) violates 3NF because dept_head depends on dept. Split it into Student(id, dept) and Department(dept, dept_head).

## Boyce-Codd normal form
BCNF is stricter than 3NF: for every non-trivial functional dependency X -> Y, X must be a superkey.
