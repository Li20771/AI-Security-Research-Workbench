"""Exact call-site identity for AI-05 §7.3.13 (Amendment 9).

**WHAT THIS IS.** A scanner that names each production call site of AI-05's two
admission entry points INDIVIDUALLY, so an approval can be recorded against the
call site rather than against a count. §7.3.13 states the standard; the obligation
it serves is §7.3.7's, as amended.

**WHAT THIS IS NOT — the limits are stated rather than overclaimed.**

```text
it is NOT a security boundary. It reads source text. It enforces nothing at run
  time, and no production path consults it.
it is NOT a completeness claim. Static analysis cannot establish the absence of
  arbitrary Python dynamic behaviour: `eval`, `exec`, dynamically constructed
  modules and code generated at run time are OUTSIDE what it can see. Nothing
  here may be described as exhaustive coverage.
silence is NOT an answer. A production call form this scanner cannot RELIABLY
  resolve is reported as UNRESOLVED and drives the check to FAIL (§7.3.13). It is
  never dropped, and an implementation whose output is identical whether such a
  form is present or absent does not satisfy the clause.
the blind-spot list is TRANSPARENCY, not acceptance. It says where the check's
  authority stops. Neither its existence nor its being non-empty makes anything
  safe, and neither is an acceptance criterion.
```

**ALIASES ARE SCOPED.** A name means what its own scope says it means. The module
is NOT one flat binding space: an assignment to a local `family` inside one
function says nothing about a `family` inside another. Bindings are collected per
scope and inherited down the lexical chain, and each name maps to a SET of
possible meanings that only ever grows, which is what makes the resolution
terminate and stops two unrelated functions from overwriting each other.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
from dataclasses import dataclass, field

__all__ = [
    "CallSiteIdentity",
    "UnresolvedCall",
    "CANONICAL_ENTRYPOINTS",
    "INTRA_PACKAGE_EDGE",
    "scan_tree",
    "group_by_key",
    "findings",
]

#: §7.3.13 — the two canonical entry-point names. An alias NEVER appears as one.
CANONICAL_ENTRYPOINTS = ("admit", "admit_to_store")

#: The package whose entry points this scanner is about.
_EVIDENCE_PACKAGE = "plugins.evidence"

#: The one intra-package edge §7.3.7's obligation has always excluded, expressed
#: as an identity key rather than as an ad-hoc filter: `admit_to_store` calling
#: `admit` inside `plugins/evidence/admission.py`.
INTRA_PACKAGE_EDGE = ("plugins/evidence/admission.py", "admit_to_store", "admit")

_UNRESOLVABLE_CALLEES = frozenset({"getattr", "__import__", "import_module"})

_LOCATION_ATTRIBUTES = ("lineno", "col_offset", "end_lineno", "end_col_offset")

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


@dataclass(frozen=True, slots=True)
class CallSiteIdentity:
    """One production call site, named individually (§7.3.13).

    `lineno` is carried for a READER and for messages. It is deliberately NOT part
    of the identity key: a line number moves when anything above it moves, which
    would re-issue approvals for unrelated edits and train a reviewer to update
    the list without reading it.
    """

    path: str
    scope: str
    entrypoint: str
    ast_path: str
    fingerprint: str
    control_context: str
    proof_kwarg: bool
    lineno: int = 0

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (self.path, self.scope, self.entrypoint, self.ast_path, self.fingerprint)


@dataclass(frozen=True, slots=True)
class UnresolvedCall:
    """A production call this scanner cannot RELIABLY resolve to an entry point.

    Reported rather than dropped. §7.3.13 makes this drive the check to FAIL; it
    MUST NOT be treated as "no call site here".
    """

    path: str
    scope: str
    lineno: int
    reason: str
    entrypoint: str | None = None


# --------------------------------------------------------------------------
# Scope-aware binding resolution
# --------------------------------------------------------------------------


@dataclass
class _Bindings:
    """What names mean in ONE scope, as sets that only ever grow.

    A set, and not a single value, is what makes the resolution monotone: two
    assignments to the same name in one scope both contribute, and neither erases
    the other. A name that resolves to MORE THAN ONE entry point is AMBIGUOUS and
    is reported rather than guessed at.
    """

    entrypoints: dict[str, set[str]] = field(default_factory=dict)
    modules: dict[str, set[str]] = field(default_factory=dict)

    def copy(self) -> "_Bindings":
        return _Bindings(
            entrypoints={name: set(values) for name, values in self.entrypoints.items()},
            modules={name: set(values) for name, values in self.modules.items()},
        )

    def add_entrypoint(self, name: str, canonical: str) -> None:
        self.entrypoints.setdefault(name, set()).add(canonical)

    def add_module(self, name: str, dotted: str) -> None:
        self.modules.setdefault(name, set()).add(dotted)

    def canonical(self, name: str) -> str | None:
        """The canonical entry point `name` denotes, or None.

        None covers three different situations, and the caller distinguishes them
        by asking `ambiguous(name)`: not bound, or bound to more than one entry
        point. An ambiguous binding is NOT resolved to one of its members.
        """
        values = self.entrypoints.get(name)
        if not values or len(values) != 1:
            return None
        return next(iter(values))

    def ambiguous(self, name: str) -> bool:
        values = self.entrypoints.get(name)
        return bool(values) and len(values) > 1


def _is_evidence_module(dotted: str) -> bool:
    return dotted == _EVIDENCE_PACKAGE or dotted.startswith(_EVIDENCE_PACKAGE + ".")


class _Scopes:
    """Lexical scopes of one module, each seeded from its parent's bindings."""

    def __init__(self, tree: ast.Module) -> None:
        self._tree = tree
        self._parents: dict[int, ast.AST | None] = {}
        self._bindings: dict[int, _Bindings] = {}
        for parent in ast.walk(tree):
            for field_name, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            self._parents[id(item)] = parent
                elif isinstance(value, ast.AST):
                    self._parents[id(value)] = parent
        for node in ast.walk(tree):
            if isinstance(node, _SCOPE_NODES):
                self._parents.setdefault(id(node), None)
        self._build()

    # -- scope construction -------------------------------------------------

    def _scope_node_of(self, node: ast.AST) -> ast.AST:
        """The innermost scope node containing `node` (the module if none)."""
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, _SCOPE_NODES):
                return current
            current = self._parents.get(id(current))
        return self._tree

    def _build(self) -> None:
        # The module scope first, then every nested scope in source order, each
        # seeded from the chain above it.
        self._bindings[id(self._tree)] = _Bindings()
        self._apply(self._tree, self._bindings[id(self._tree)])
        for node in ast.walk(self._tree):
            if isinstance(node, _SCOPE_NODES):
                parent = self._scope_node_of(self._parents.get(id(node)) or self._tree)
                seed = self._bindings.get(id(parent), self._bindings[id(self._tree)]).copy()
                self._bindings[id(node)] = seed
                self._apply(node, seed)

    def _apply(self, scope: ast.AST, bindings: _Bindings) -> None:
        """Apply the statements OWNED by `scope` to its bindings, to a fixed point.

        Only statements whose nearest enclosing scope IS this scope are applied, so
        a local inside one function cannot reach another. The loop is bounded by
        the number of assignments in the scope, because bindings only grow.
        """
        statements = [
            node
            for node in ast.walk(scope)
            if self._scope_node_of(node) is scope and isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign))
        ]
        for _ in range(len(statements) + 2):
            before = (sum(len(v) for v in bindings.entrypoints.values()), sum(len(v) for v in bindings.modules.values()))
            for node in statements:
                self._apply_one(node, bindings)
            after = (sum(len(v) for v in bindings.entrypoints.values()), sum(len(v) for v in bindings.modules.values()))
            if before == after:
                return

    def _apply_one(self, node: ast.AST, bindings: _Bindings) -> None:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _EVIDENCE_PACKAGE + ("." + module if module else "")
            for alias in node.names:
                local = alias.asname or alias.name
                target = f"{module}.{alias.name}" if module else alias.name
                if alias.name in CANONICAL_ENTRYPOINTS and _is_evidence_module(module):
                    bindings.add_entrypoint(local, alias.name)
                elif _is_evidence_module(target):
                    bindings.add_module(local, target)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                if _is_evidence_module(alias.name):
                    bindings.add_module(local, alias.name)
        else:  # Assign / AnnAssign
            value = node.value
            if value is None:
                return
            resolved = self._resolve_value(value, bindings)
            if resolved is None:
                return
            kind, dotted = resolved
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if kind == "entrypoint":
                    bindings.add_entrypoint(target.id, dotted)
                else:
                    bindings.add_module(target.id, dotted)

    # -- lookup -------------------------------------------------------------

    def for_node(self, node: ast.AST) -> _Bindings:
        return self._bindings.get(id(self._scope_node_of(node)), self._bindings[id(self._tree)])

    def scope_name(self, node: ast.AST) -> str:
        names: list[str] = []
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(current.name)
            current = self._parents.get(id(current))
        if not names:
            return "<module>"
        names.reverse()
        return ".".join(names)

    def parents(self) -> dict[int, ast.AST]:
        return {key: value for key, value in self._parents.items() if value is not None}

    def _resolve_value(self, node: ast.expr, bindings: _Bindings) -> tuple[str, str] | None:
        if isinstance(node, ast.Name):
            canonical = bindings.canonical(node.id)
            if canonical is not None:
                return ("entrypoint", canonical)
            modules = bindings.modules.get(node.id)
            if modules and len(modules) == 1:
                return ("module", next(iter(modules)))
            return None
        if isinstance(node, ast.Attribute):
            dotted = self.dotted(node, bindings)
            if dotted is None:
                return None
            head, _, tail = dotted.rpartition(".")
            if tail in CANONICAL_ENTRYPOINTS and _is_evidence_module(head):
                return ("entrypoint", tail)
            if _is_evidence_module(dotted):
                return ("module", dotted)
        return None

    def dotted(self, node: ast.expr, bindings: _Bindings) -> str | None:
        """The dotted path an expression denotes, or None if it is not a name chain.

        Each head is expanded through the MODULE bindings of its scope, and only
        through the ones that are unambiguous: substituting one of several possible
        modules would invent a path the source does not name.
        """
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        parts.append(current.id)
        parts.reverse()
        head = parts[0]
        modules = bindings.modules.get(head)
        if modules and len(modules) == 1:
            return ".".join([next(iter(modules))] + parts[1:])
        return ".".join(parts)


# --------------------------------------------------------------------------
# Identity construction
# --------------------------------------------------------------------------


def _ast_path(parents: dict[int, ast.AST], node: ast.AST) -> str:
    """The child-field/index path from the module root to `node` (§7.3.13).

    Structure, not position: built from AST field names and list indices, so it
    does not move when unrelated lines shift, and it DOES change when a call moves
    within its scope — which is part of what lets a substitution whose count is
    unchanged be seen.
    """
    steps: list[str] = []
    current: ast.AST | None = node
    while current is not None and id(current) in parents:
        parent = parents[id(current)]
        field_name = None
        for name, value in ast.iter_fields(parent):
            if value is current:
                field_name = name
                break
            if isinstance(value, list) and any(item is current for item in value):
                index = next(i for i, item in enumerate(value) if item is current)
                field_name = f"{name}[{index}]"
                break
        if field_name is None:
            break
        steps.append(field_name)
        current = parent
    steps.reverse()
    return ".".join(steps) if steps else "<module>"


def _control_context(parents: dict[int, ast.AST], node: ast.AST) -> str:
    """The chain of enclosing STATEMENT kinds, outermost first (§7.3.13)."""
    kinds: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.stmt) and not isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            kinds.append(type(current).__name__)
        current = parents.get(id(current))
    kinds.reverse()
    return "/".join(kinds)


def _fingerprint(call: ast.Call, canonical: str, parents: dict[int, ast.AST]) -> str:
    """A canonical digest over the call's OWN subtree (§7.3.13).

    The callee is NORMALISED to the canonical entry-point name, so two spellings
    that reach the same entry point agree on the callee and differ, if at all, on
    their arguments. Location attributes are excluded, which is what makes the
    fingerprint stable against unrelated edits and sensitive to edits INSIDE the
    call. The subtree is rebuilt rather than mutated so the caller's tree is left
    alone.
    """
    rebuilt = ast.Call(
        func=ast.Name(id=canonical, ctx=ast.Load()),
        args=list(call.args),
        keywords=list(call.keywords),
    )
    # `include_attributes=False` is what drops lineno/col_offset from the dump, so
    # no copying is needed: the children may be shared with the caller's tree
    # precisely because no location attribute is read.
    payload = ast.dump(rebuilt, annotate_fields=True, include_attributes=False)
    payload += "\x00" + _control_context(parents, call)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _proof_kwarg(call: ast.Call) -> bool:
    """Whether `producer_proof` is passed EXPLICITLY as a keyword (§7.3.13).

    A `**mapping` expansion does NOT satisfy this: the argument is then not
    verifiable from the source, and the clause refuses it rather than assuming the
    key is inside the expansion.
    """
    return any(keyword.arg == "producer_proof" for keyword in call.keywords)


def _named_entrypoint(func: ast.expr) -> str | None:
    """The entry-point NAME this callee spells, or None if it spells none.

    Carried on a finding so the one intra-package edge §7.3.7 has always excluded
    can be excluded from the UNRESOLVED list too, by the same (path, scope, name)
    key the observed side uses — rather than by a looser rule that would silence
    unrelated findings in the same function.
    """
    if isinstance(func, ast.Name) and func.id in CANONICAL_ENTRYPOINTS:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr in CANONICAL_ENTRYPOINTS:
        return func.attr
    for child in ast.walk(func):
        if isinstance(child, ast.Name) and child.id in CANONICAL_ENTRYPOINTS:
            return child.id
        if isinstance(child, ast.Attribute) and child.attr in CANONICAL_ENTRYPOINTS:
            return child.attr
        if isinstance(child, ast.Constant) and child.value in CANONICAL_ENTRYPOINTS:
            return str(child.value)
    return None


def _names_an_entrypoint(node: ast.AST) -> bool:
    """Whether `node` mentions a canonical entry-point NAME in any spelling.

    The question this answers is narrow on purpose: the unresolved-form rule is
    about calls that could BE an admission write. A call that never names an entry
    point — `hashlib.sha256(...)`, `payload.get(...)` — is not an unresolved
    admission call, and reporting it would bury the real findings in noise.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in CANONICAL_ENTRYPOINTS:
            return True
        if isinstance(child, ast.Attribute) and child.attr in CANONICAL_ENTRYPOINTS:
            return True
        if isinstance(child, ast.Constant) and child.value in CANONICAL_ENTRYPOINTS:
            return True
    return False


def _unresolvable_reason(call: ast.Call, scopes: _Scopes, bindings: _Bindings) -> str | None:
    """Why this call's real target cannot be determined, or None if it can.

    FIRES ONLY ON CALLS THAT NAME AN ENTRY POINT AND CANNOT BE RESOLVED. A call
    that never names one is not an admission call at all, and the rule does not
    reach it — otherwise every attribute chain in the repository would be reported
    and the real findings would be invisible.
    """
    callee = call.func

    # A call whose RESULT is immediately called: `getattr(m, "admit")(...)`,
    # `partial(admit_to_store, store=s)(...)`, `registry["admit"](...)`.
    if isinstance(callee, ast.Call):
        inner = callee.func
        if isinstance(inner, ast.Name) and inner.id in _UNRESOLVABLE_CALLEES and _names_an_entrypoint(callee):
            return f"reflective acquisition via `{inner.id}(...)`"
        if isinstance(inner, ast.Attribute) and inner.attr in _UNRESOLVABLE_CALLEES and _names_an_entrypoint(callee):
            return f"reflective acquisition via `.{inner.attr}(...)`"
        inner_name = inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", None)
        if inner_name == "partial" and _names_an_entrypoint(callee):
            return "partial application over an entry point"

    # A subscript callee: `registry["admit"](...)`, `callables[0](...)` where the
    # slice names an entry point.
    if isinstance(callee, ast.Subscript) and _names_an_entrypoint(callee):
        return "dispatch through a container (subscript)"

    # A bare name that is an entry-point name but does not resolve here: a
    # parameter, or a binding this scope does not establish.
    if isinstance(callee, ast.Name) and callee.id in CANONICAL_ENTRYPOINTS:
        if scopes is not None and bindings.ambiguous(callee.id):
            return f"`{callee.id}` resolves to more than one entry point in this scope"
        return f"`{callee.id}` is called but not bound to an entry point in this scope"

    # An attribute whose tail is an entry-point name but whose root is unknown:
    # a parameter-rooted chain, i.e. an object handed in from outside.
    if isinstance(callee, ast.Attribute) and callee.attr in CANONICAL_ENTRYPOINTS:
        dotted = scopes.dotted(callee, bindings)
        if dotted is None:
            return "callee is an attribute chain with no resolvable root"
        root = dotted.split(".", 1)[0]
        if root not in bindings.modules and root not in bindings.entrypoints:
            return f"callee rooted in `{root}`, which this scope does not bind"

    return None


def scan_tree(
    root: pathlib.Path, *, skip_paths: tuple[str, ...] = ()
) -> tuple[list[CallSiteIdentity], list[UnresolvedCall]]:
    """Every candidate call site and every unresolvable form under `root`.

    `skip_paths` names path parts to exclude (the `tests` tree, for a PRODUCTION
    check), and it is named rather than assumed.
    """
    found: list[CallSiteIdentity] = []
    unresolved: list[UnresolvedCall] = []
    root = pathlib.Path(root)
    for path in sorted(root.rglob("*.py")):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if any(part in path.parts for part in skip_paths):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        relative = path.relative_to(root).as_posix()
        scopes = _Scopes(tree)
        parents = scopes.parents()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            bindings = scopes.for_node(node)
            canonical = _canonical_of(node.func, scopes, bindings)
            if canonical is None:
                reason = _unresolvable_reason(node, scopes, bindings)
                if reason is not None:
                    unresolved.append(
                        UnresolvedCall(
                            path=relative,
                            scope=scopes.scope_name(node),
                            lineno=node.lineno,
                            reason=reason,
                            entrypoint=_named_entrypoint(node.func),
                        )
                    )
                continue
            found.append(
                CallSiteIdentity(
                    path=relative,
                    scope=scopes.scope_name(node),
                    entrypoint=canonical,
                    ast_path=_ast_path(parents, node),
                    fingerprint=_fingerprint(node, canonical, parents),
                    control_context=_control_context(parents, node),
                    proof_kwarg=_proof_kwarg(node),
                    lineno=node.lineno,
                )
            )
    return found, unresolved


def _canonical_of(func: ast.expr, scopes: _Scopes, bindings: _Bindings) -> str | None:
    """The canonical entry point this callee resolves to, or None."""
    if isinstance(func, ast.Name):
        return bindings.canonical(func.id)
    if isinstance(func, ast.Attribute):
        if func.attr not in CANONICAL_ENTRYPOINTS:
            return None
        dotted = scopes.dotted(func, bindings)
        if dotted is None:
            return None
        if _is_evidence_module(dotted.rsplit(".", 1)[0]):
            return func.attr
    return None


# --------------------------------------------------------------------------
# The approved set, and the comparison
# --------------------------------------------------------------------------


def group_by_key(
    identities: list[CallSiteIdentity],
) -> dict[tuple[str, str, str, str, str], CallSiteIdentity]:
    """The OBSERVED mapping, keyed by identity (§7.3.13)."""
    return {identity.key: identity for identity in identities}


def findings(
    observed: list[CallSiteIdentity],
    approved: dict[tuple[str, str, str, str, str], CallSiteIdentity] | None,
    unresolved: list[UnresolvedCall] | None = None,
    *,
    exclude_intra_package_edge: bool = True,
) -> list[str]:
    """Everything that makes the observed set differ from the approved set.

    AN EMPTY LIST IS THE ONLY CLEAN RESULT. The comparison is MAPPING EQUALITY in
    both directions: an identity present on one side only is a finding, whatever
    the counts say. This function NEVER compares counts, because equality of a
    count is not evidence that individual call sites were approved (§7.3.13).
    """
    approved = {} if approved is None else approved
    unresolved = [] if unresolved is None else unresolved
    problems: list[str] = []

    observed_map = group_by_key(observed)
    if exclude_intra_package_edge:
        observed_map = {
            key: value
            for key, value in observed_map.items()
            if (key[0], key[1], key[2]) != INTRA_PACKAGE_EDGE
        }

    for key, identity in sorted(observed_map.items()):
        if key not in approved:
            problems.append(
                f"UNAPPROVED call site: {identity.path}:{identity.lineno} "
                f"scope={identity.scope} entrypoint={identity.entrypoint} "
                f"ast_path={identity.ast_path} fingerprint={identity.fingerprint}"
            )
    for key, identity in sorted(approved.items()):
        if key not in observed_map:
            problems.append(
                f"APPROVED call site NOT FOUND: {identity.path} scope={identity.scope} "
                f"entrypoint={identity.entrypoint} ast_path={identity.ast_path} "
                f"fingerprint={identity.fingerprint}"
            )
    for identity in sorted(observed_map.values(), key=lambda item: (item.path, item.lineno)):
        if not identity.proof_kwarg:
            problems.append(
                f"MISSING producer_proof KEYWORD: {identity.path}:{identity.lineno} "
                f"scope={identity.scope} — a `**mapping` expansion does not satisfy "
                f"§7.3.13's proof_kwarg field"
            )
    for call in sorted(unresolved, key=lambda item: (item.path, item.lineno)):
        if exclude_intra_package_edge and (
            call.path,
            call.scope,
            call.entrypoint,
        ) == INTRA_PACKAGE_EDGE:
            continue
        problems.append(
            f"UNRESOLVED production call form: {call.path}:{call.lineno} "
            f"scope={call.scope} — {call.reason}. §7.3.13 makes this FAIL rather "
            f"than count as 'no call site'"
        )
    return problems
