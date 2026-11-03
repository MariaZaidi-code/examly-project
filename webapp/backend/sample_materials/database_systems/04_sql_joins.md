# SQL joins and set operations

A join combines rows from two relations using a matching condition. The inner join returns only pairs that satisfy the condition, so unmatched rows disappear from the result. The left outer join keeps every row of the left relation and fills missing right columns with null values.

## Outer and cross joins

A right outer join keeps every row of the right relation, while a full outer join keeps unmatched rows from both sides. The cross join returns the Cartesian product and is useful mainly for building combinations or calendars. A self join connects a table to itself, which is how managers and employees or prerequisites and courses are represented.

## Writing correct join conditions

Join conditions belong in the ON clause, while filters on the preserved side belong in the WHERE clause only when outer join semantics are understood. Putting a filter on the right table in WHERE silently turns a left join into an inner join, a common mistake in student queries. Aliasing each table keeps multi table queries readable.

## Performance notes

The optimizer may reorder inner joins because they are associative, but outer joins constrain that freedom. Indexes on join keys reduce the cost of nested loop joins, and hash joins help when both inputs are large. Exam questions often ask for the difference between where and having, so remember that where filters rows while having filters groups.
