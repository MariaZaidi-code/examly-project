# Operating Systems: Deadlock Handling (synthetic lecture notes)

## Definition
A deadlock occurs when a set of processes each hold a resource while waiting for a resource held by another process in the set, so none can proceed.

## Coffman conditions
Deadlock requires four conditions at once: mutual exclusion, hold and wait, no preemption, and circular wait. Breaking any one condition prevents deadlock.

## Strategies
Prevention breaks one Coffman condition, for example by imposing a global lock ordering to avoid circular wait. Avoidance, such as the Banker's algorithm, grants a request only if the system stays in a safe state. Detection builds a wait-for graph and looks for cycles, then recovers by killing a process or preempting resources. Ignoring the problem, the ostrich approach, is used by many general purpose systems.

## Safe state
A state is safe if there is an order in which every process can finish using the resources still available plus those released by earlier processes.
