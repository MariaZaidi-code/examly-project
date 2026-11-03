# Computer Networks: IP Subnetting (synthetic lecture notes)

## CIDR notation
A CIDR prefix such as 192.168.10.0/24 says that the first 24 bits identify the network and the remaining 8 bits identify hosts.

## Counting hosts
With h host bits a subnet has 2^h addresses, of which 2^h - 2 are usable because the first address is the network address and the last is the broadcast address. A /26 has 6 host bits, so 64 addresses and 62 usable hosts.

## Subnetting procedure
To split a network into more subnets, borrow bits from the host portion. Borrowing n bits creates 2^n subnets. The subnet mask is found by setting all network and borrowed bits to one. A /26 mask is 255.255.255.192.

## Routing
Routers forward packets using the longest prefix match against the routing table.
