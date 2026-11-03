# Normalization and functional dependencies

Normalization organizes relations so that redundancy and update anomalies are reduced. A functional dependency X to Y means that every value of X determines exactly one value of Y. Database designers use dependencies to decide how relations should be decomposed without losing information.

## First and second normal form

A relation is in first normal form when every attribute holds a single atomic value. Repeating groups and comma separated lists violate first normal form because they hide multiple facts inside one column. Second normal form removes partial dependencies, so a non key attribute must depend on the whole composite key rather than part of it.

## Third normal form

Third normal form removes transitive dependencies so that non key attributes depend only on the primary key. If A determines B and B determines C, then C depends on A only through B and the relation is not in third normal form. The classic example is Student with columns id, department and department head, where the head depends on the department rather than directly on the student. Splitting that relation into Student and Department removes the transitive dependency and prevents inconsistent updates.

## Boyce Codd and denormalization

Boyce Codd normal form strengthens third normal form by requiring every determinant to be a candidate key. Normalization reduces duplication but adds joins at query time, so warehouses sometimes denormalize deliberately to speed up analytical reads. Normalizing exam notes helps students reason about keys, dependencies and controlled redundancy.
