# Terminal

Controlled terminal execution adapter.

The adapter must check Guard policy before command execution and emit structured Evidence.

High-impact operations require explicit Guard approval.

## The adapter does not use a shell

`AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md` §11.1 forbids a shell interpreter outright: an operation
executes an argv vector, as a list, with no shell between AI-06 and the process. There is no
`shell=True`, no `sh -c`, no `cmd /c`, and no string interpolation into a command line. Shell
metacharacters (`;`, `|`, `$()`, `&&`) reach the program as ordinary arguments rather than being
interpreted.

This note replaces an earlier sentence — *"High-impact shell operations require explicit Guard
approval"* — which said the same thing but could be misread as licensing a shell interpreter. The
requirement is unchanged: which operations need approval was always the question, never how a
command is run.
