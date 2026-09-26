# Contributing

## Standard flow
1. Start from current main.
2. Create a task branch.
3. Record base SHA.
4. Make a small coherent change.
5. Run relevant validation.
6. Review the diff.
7. Open a pull request.
8. Merge only after the required approval gate.

## Agent rule
Agents follow the same Git workflow. Model confidence never substitutes for test evidence.

## Status semantics
PASS = executed and supported by evidence.
FAIL = executed and failed.
BLOCKED = required action or environment unavailable or denied.
NOT_RUN = intentionally not executed.
UNKNOWN = insufficient evidence.

Do not convert BLOCKED, NOT_RUN, or UNKNOWN into PASS.