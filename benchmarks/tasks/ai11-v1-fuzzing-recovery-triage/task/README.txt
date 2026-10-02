Tier B: this task needs an exclusive vcan0 and CAP_NET_ADMIN.
On a host without them it is BLOCKED, and BLOCKED is recorded rather than
dropped, skipped silently, or counted as a failure.
