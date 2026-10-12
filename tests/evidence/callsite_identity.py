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
    "ScanFailure",
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

#: The ONE intra-package call site §7.3.7's obligation has always excluded:
#: `plugins/evidence/admission.py`'s own `admit_to_store` calling its own `admit`.
#:
#: THE TRIPLE CANNOT NAME A CALL SITE ON ITS OWN, AND THE EXCEPTION DOES NOT
#: PRETEND IT CAN. A second `admit(...)` in the same scope shares all three
#: fields, so an exclusion over the triple alone would swallow that second call —
#: which is exactly what §7.3.13's exact-call-site standard forbids. The exception
#: is therefore bounded by UNIQUENESS in `findings()`: it excuses AT MOST ONE
#: matching entry per side, and more than one match means NOTHING is excused.
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
    callee: str
    ast_path: str
    fingerprint: str
    control_context: str
    proof_kwarg: bool
    lineno: int = 0

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        """The identity compared against the approved set (§7.3.13).

        `callee` IS PART OF THE IDENTITY, and it is the ORIGINAL source form of
        the callee expression — not the canonical entry point it resolves to. The
        canonical name is carried separately, because it answers a DIFFERENT
        question: "which entry point does this reach". Two calls that reach the
        same entry point through different expressions are two DIFFERENT call
        sites, and an approval of one is not an approval of the other. Recording
        only the canonical name would let a direct call and an alias call at the
        same AST path, with the same arguments, share one identity.
        """
        return (self.path, self.scope, self.entrypoint, self.callee, self.ast_path, self.fingerprint)


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


@dataclass(frozen=True, slots=True)
class ScanFailure:
    """A file the scan could not READ or PARSE.

    A file that could not be read is a file whose call sites are UNKNOWN, and
    "unknown" is not "none". Reporting it as an auditable failure is the same rule
    §7.3.13 applies to an unresolvable CALL, applied to an unresolvable MODULE: a
    scanner that silently skipped it would be reporting silence as safety.
    """

    path: str
    reason: str


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
    #: Names bound to a callable this scanner CANNOT trace, where the right-hand
    #: side plausibly denotes an admission entry point. The value is the reason.
    #: A call through such a name is reported, not ignored — that is the whole
    #: point of carrying the taint instead of only checking the immediate form.
    tainted: dict[str, str] = field(default_factory=dict)
    #: Names bound to a plain string, so `field = "admit"` can be followed and an
    #: attribute name that is a VARIABLE is not mistaken for an unknown one.
    constants: dict[str, set[str]] = field(default_factory=dict)
    #: Names that are aliases of an acquisition callable: `from functools import
    #: partial as p` makes `p` mean `partial`. Without this, an aliased
    #: acquisition is a different spelling of the same hole.
    acquirers: dict[str, str] = field(default_factory=dict)
    #: Names bound to a module that CARRIES an acquisition callable, so
    #: `ft.partial(...)` is recognised when `ft` is `functools`.
    acquirer_modules: set[str] = field(default_factory=set)

    def copy(self) -> "_Bindings":
        return _Bindings(
            entrypoints={name: set(values) for name, values in self.entrypoints.items()},
            modules={name: set(values) for name, values in self.modules.items()},
            tainted=dict(self.tainted),
            constants={name: set(values) for name, values in self.constants.items()},
            acquirers=dict(self.acquirers),
            acquirer_modules=set(self.acquirer_modules),
        )

    def taint(self, name: str, reason: str) -> None:
        self.tainted.setdefault(name, reason)

    def add_constant(self, name: str, value: str) -> None:
        self.constants.setdefault(name, set()).add(value)

    def constant(self, name: str) -> str | None:
        """The single string `name` is bound to, or None if it is not one value."""
        values = self.constants.get(name)
        if not values or len(values) != 1:
            return None
        return next(iter(values))

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


#: Call forms that ACQUIRE a callable this scanner cannot follow to its target.
_UNTRACEABLE_ACQUISITIONS = frozenset({"getattr", "__import__", "import_module", "partial"})

#: The attribute names those callables are known by.
_ACQUIRER_ATTRS = _UNTRACEABLE_ACQUISITIONS

#: The modules that carry them. A local name bound to one of these is recognised
#: as a carrier, so `ft.partial(...)` is the same form as `functools.partial(...)`.
_ACQUIRER_MODULES = frozenset({"functools", "builtins", "importlib"})


def _callee_form(func: ast.expr) -> str:
    """The ORIGINAL source form of a callee expression (§7.3.13).

    THIS IS NOT THE CANONICAL ENTRY POINT. `admit`, `submit` and `adm.admit` are
    three different forms that may all resolve to `admit`, and recording the
    canonical name alone would collapse them into one identity. Location
    attributes are excluded so the form does not move with the lines above it.
    """
    return ast.dump(func, annotate_fields=True, include_attributes=False)


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
            before = self._size(bindings)
            for node in statements:
                self._apply_one(node, bindings)
            after = self._size(bindings)
            if before == after:
                return

    @staticmethod
    def _size(bindings: _Bindings) -> tuple[int, int, int, int, int, int]:
        """A monotone size, so the fixed point terminates.

        `tainted` is counted too: a taint established late in a pass must still
        make the NEXT pass run, or a chain like `a = getattr(...)` / `b = a` would
        stop one step short of the name that is actually called. The same holds for
        a string constant and for an acquirer alias discovered late.
        """
        return (
            sum(len(values) for values in bindings.entrypoints.values()),
            sum(len(values) for values in bindings.modules.values()),
            len(bindings.tainted),
            sum(len(values) for values in bindings.constants.values()),
            len(bindings.acquirers),
            len(bindings.acquirer_modules),
        )

    def _apply_one(self, node: ast.AST, bindings: _Bindings) -> None:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _EVIDENCE_PACKAGE + ("." + module if module else "")
            root = module.split(".", 1)[0]
            for alias in node.names:
                local = alias.asname or alias.name
                target = f"{module}.{alias.name}" if module else alias.name
                if root in _ACQUIRER_MODULES and alias.name in _ACQUIRER_ATTRS:
                    # `from functools import partial as p` — `p` IS `partial`, and
                    # an aliased acquisition is the same hole under another name.
                    bindings.acquirers[local] = alias.name
                elif alias.name in CANONICAL_ENTRYPOINTS and _is_evidence_module(module):
                    bindings.add_entrypoint(local, alias.name)
                elif _is_evidence_module(target):
                    bindings.add_module(local, target)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                if alias.name.split(".", 1)[0] in _ACQUIRER_MODULES:
                    bindings.acquirer_modules.add(local)
                if not _is_evidence_module(alias.name):
                    continue
                # AN UNALIASED DOTTED IMPORT BINDS ITS ROOT, NOT THE FULL PATH.
                # `import plugins.evidence` binds the name `plugins` to the module
                # `plugins` — the submodule is reachable AS AN ATTRIBUTE. Binding
                # `plugins` to `plugins.evidence` made the next expansion produce
                # `plugins.evidence.evidence.admit`: a path that does not exist,
                # which happened to be classified as evidence anyway and so hid the
                # defect instead of failing on it.
                if alias.asname:
                    bindings.add_module(local, alias.name)
                else:
                    bindings.add_module(local, alias.name.split(".", 1)[0])
        else:  # Assign / AnnAssign
            value = node.value
            if value is None:
                return
            # `Assign` carries `targets`, `AnnAssign` carries `target` — normalized
            # here so every branch below treats them the same way.
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                # `field = "admit"` — the name and the string are the same thing,
                # and an attribute name that is a VARIABLE must not be read as an
                # unknown one when its value is sitting right there.
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings.add_constant(target.id, value.value)
                return
            acquirer = self.acquirer_name(value, bindings)
            if acquirer is not None:
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings.acquirers[target.id] = acquirer
                return
            resolved = self._resolve_value(value, bindings)
            if resolved is None:
                # THE VALUE COULD NOT BE RESOLVED. Before giving up, ask whether it
                # is an UNTRACEABLE ACQUISITION of something that may be an entry
                # point; if it is, the NAME it is bound to carries that fact
                # forward, so a later call THROUGH that name is reported rather
                # than looking like an ordinary unknown call.
                reason = self._taint_reason(value, bindings)
                if reason is not None:
                    for target in targets:
                        if isinstance(target, ast.Name):
                            bindings.taint(target.id, reason)
                return
            kind, dotted = resolved
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if kind == "entrypoint":
                    bindings.add_entrypoint(target.id, dotted)
                else:
                    bindings.add_module(target.id, dotted)

    def acquirer_name(self, func: ast.expr, bindings: _Bindings) -> str | None:
        """The acquisition callable a callee denotes, following simple aliases.

        Bounded on purpose: it follows a local alias and a module attribute whose
        root IS one of the modules that carries these callables. It does not follow
        a callable passed in from outside, and it does not claim to.
        """
        if isinstance(func, ast.Name):
            if func.id in _UNTRACEABLE_ACQUISITIONS:
                return func.id
            return bindings.acquirers.get(func.id)
        if isinstance(func, ast.Attribute) and func.attr in _ACQUIRER_ATTRS:
            root = self.dotted(func, bindings)
            if root is None:
                return None
            head = root.split(".", 1)[0]
            if head in bindings.acquirer_modules or head in _ACQUIRER_MODULES:
                return func.attr
        return None

    def _is_evidence_receiver(self, node: ast.expr, bindings: _Bindings) -> bool:
        """Whether `node` denotes an Evidence module through this scope's bindings.

        A NAME MATCH IS NOT ENOUGH. `import plugins.evidence as ev` binds `ev`, and
        a check that only recognised the spelling `evidence` would miss it — which
        is how a `getattr(ev, <dynamic>)` could slip past.
        """
        dotted = self.dotted(node, bindings)
        return dotted is not None and _is_evidence_module(dotted)

    def _constant_string(self, node: ast.expr | None, bindings: _Bindings) -> str | None:
        """The string value an expression is known to hold, or None."""
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return bindings.constant(node.id)
        return None

    def _taint_reason(self, value: ast.expr, bindings: _Bindings) -> str | None:
        """Why `value` is a callable this scanner cannot trace, or None.

        The rule is deliberately narrow: the value must PLAUSIBLY denote an
        admission entry point. Everything else is left alone, because reporting
        every unresolvable expression in a repository buries the real findings.
        """
        if isinstance(value, ast.Name):
            return bindings.tainted.get(value.id)
        if isinstance(value, ast.Attribute):
            dotted = self.dotted(value, bindings)
            root = (dotted or value.attr).split(".", 1)[0]
            if root in bindings.tainted:
                return bindings.tainted[root]
            if value.attr in CANONICAL_ENTRYPOINTS and (
                dotted is None or root not in bindings.modules
            ):
                return (
                    f"`{value.attr}` reached through `{root}`, whose value this "
                    f"scope does not resolve"
                )
            return None
        if isinstance(value, ast.Subscript):
            if self._mentions_evidence(value, bindings):
                return "extraction from a container, which this scanner cannot index"
            return None
        if isinstance(value, ast.Call):
            acquirer = self.acquirer_name(value.func, bindings)
            if acquirer is not None:
                return self._acquisition_reason(acquirer, value, bindings)
            if isinstance(value.func, ast.expr):
                return self._taint_reason(value.func, bindings)
        return None

    def _acquisition_reason(self, acquirer: str, call: ast.Call, bindings: _Bindings) -> str | None:
        """Why an acquisition call yields an untraceable callable, or None.

        THE RECEIVER DECIDES, NOT THE SPELLING OF THE ATTRIBUTE. When the object a
        callable is taken FROM is an Evidence module, an attribute name the scanner
        cannot resolve MUST NOT be assumed harmless: `getattr(ev, field)` may be
        `admit` at run time, and "we could not read the name" is not "it is not an
        entry point".
        """
        if acquirer == "getattr" and call.args:
            receiver = call.args[0]
            if self._is_evidence_receiver(receiver, bindings):
                attribute = call.args[1] if len(call.args) >= 2 else None
                resolved = self._constant_string(attribute, bindings)
                if resolved is None:
                    return (
                        "a callable acquired from the EVIDENCE PACKAGE by an "
                        "attribute name this scanner cannot resolve — that name "
                        "cannot be assumed NOT to be an admission entry point"
                    )
                if resolved in CANONICAL_ENTRYPOINTS:
                    return (
                        f"`getattr(<evidence module>, {resolved!r})` — a callable "
                        f"acquired by name rather than called directly"
                    )
                return None
        if self._mentions_evidence(call, bindings):
            return (
                f"`{acquirer}(...)`, whose result is a callable this scanner "
                f"cannot trace to a target"
            )
        return None

    def _mentions_evidence(self, node: ast.AST, bindings: _Bindings) -> bool:
        """Whether `node` names an entry point or the evidence package, in any form.

        BINDINGS-AWARE, and that is the point. A name bound to an Evidence module
        counts — `import plugins.evidence as ev` makes `ev` a mention — and so does
        a name bound to a string that reads `"admit"`. A check that only matched
        the literal spellings would let an aliased or variable-carried mention
        through.
        """
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if child.id in CANONICAL_ENTRYPOINTS or child.id in bindings.modules:
                    return True
                # A RESOLVED ENTRY ALIAS COUNTS. `from plugins.evidence import admit
                # as persist` makes `persist` an entry point in this scope, and
                # `partial(persist, ...)` is an acquisition of one. Checking only
                # the literal spellings would miss it; checking the SCOPE'S OWN
                # BINDINGS catches it without a special case per name — including
                # an AMBIGUOUS binding, which is present here and fails closed
                # later rather than being skipped.
                if child.id in bindings.entrypoints:
                    return True
                value = bindings.constant(child.id)
                if value is not None and (
                    value in CANONICAL_ENTRYPOINTS or _EVIDENCE_PACKAGE in value
                ):
                    return True
            elif isinstance(child, ast.Attribute):
                if child.attr in CANONICAL_ENTRYPOINTS:
                    return True
            elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                if child.value in CANONICAL_ENTRYPOINTS or _EVIDENCE_PACKAGE in child.value:
                    return True
        return False

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


def _fingerprint(call: ast.Call, parents: dict[int, ast.AST]) -> str:
    """A canonical digest over the call's ARGUMENTS and its control context.

    THE CALLEE IS DELIBERATELY REPLACED BY A PLACEHOLDER HERE. It is not dropped:
    it is recorded as its own identity field (`callee`, the original source form),
    because the two answer different questions. Normalising the callee INTO this
    digest — as an earlier revision did — would have made a direct call and an
    alias call at the same AST path, with the same arguments, fingerprint alike,
    and §7.3.13 treats those as two different call sites.

    Location attributes are excluded, which is what makes the digest stable
    against unrelated edits and sensitive to edits INSIDE the call.

    THE DIGEST, STATED SO IT IS NOT ASSUMED:

        algorithm   SHA-256 over the UTF-8 bytes of the canonical `ast.dump` of
                    the call's arguments and keywords, a NUL separator, and the
                    enclosing statement-kind chain
        output      the FULL 64-character lowercase hexadecimal digest. IT IS NOT
                    TRUNCATED. An earlier revision took the first 32 characters,
                    which is 128 bits; that is not what this returns now, and a
                    reader comparing a stored identity against this function's
                    output must compare all 64 characters
        collision   the identity inherits SHA-256's collision resistance and
                    nothing stronger. It is an ASSUMPTION, not a proof: a
                    collision would make two different calls share one identity,
                    and this scanner does not attempt to detect one. The
                    assumption is written down because the approval's meaning
                    depends on it — an approval is only as specific as the
                    identity that carries it
    """
    rebuilt = ast.Call(
        func=ast.Name(id="<callee>", ctx=ast.Load()),
        args=list(call.args),
        keywords=list(call.keywords),
    )
    payload = ast.dump(rebuilt, annotate_fields=True, include_attributes=False)
    payload += "\x00" + _control_context(parents, call)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    # The acquirer is resolved through the SAME alias-following helper the taint
    # rule uses, so `p(...)()` after `from functools import partial as p` is the
    # same form under another name rather than a new hole.
    if isinstance(callee, ast.Call):
        acquirer = scopes.acquirer_name(callee.func, bindings)
        if acquirer is not None:
            reason = scopes._acquisition_reason(acquirer, callee, bindings)
            if reason is not None:
                return f"immediately-invoked acquisition — {reason}"

    # A subscript callee: `registry["admit"](...)`, `callables[0](...)` where the
    # slice names an entry point.
    if isinstance(callee, ast.Subscript) and _names_an_entrypoint(callee):
        return "dispatch through a container (subscript)"

    # A NAME. Three ways it can fail to resolve, and they are reported separately
    # because they call for different fixes.
    if isinstance(callee, ast.Name):
        taint = bindings.tainted.get(callee.id)
        if taint is not None:
            return (
                f"`{callee.id}` was bound to {taint}, and is called HERE — the "
                f"acquisition form is unsupported, so the call's real target "
                f"cannot be determined"
            )
        if bindings.ambiguous(callee.id):
            return (
                f"`{callee.id}` resolves to MORE THAN ONE entry point in this "
                f"scope ({', '.join(sorted(bindings.entrypoints[callee.id]))}), so "
                f"which one it denotes cannot be determined"
            )
        if callee.id in CANONICAL_ENTRYPOINTS:
            return (
                f"`{callee.id}` is called but not bound to an entry point in this "
                f"scope — a parameter, or a binding this scope does not establish"
            )
        return None

    # AN ATTRIBUTE. A tainted root is reported first: the chain's real target is
    # already unknown, and the tail's spelling does not make it known again.
    if isinstance(callee, ast.Attribute):
        dotted = scopes.dotted(callee, bindings)
        root = (dotted or callee.attr).split(".", 1)[0]
        if root in bindings.tainted:
            return (
                f"`{dotted or callee.attr}` is reached through `{root}`, which was "
                f"bound to {bindings.tainted[root]}"
            )
        if callee.attr in CANONICAL_ENTRYPOINTS:
            if dotted is None:
                return "callee is an attribute chain with no resolvable root"
            if root not in bindings.modules and root not in bindings.entrypoints:
                return f"callee rooted in `{root}`, which this scope does not bind"

    return None


def scan_tree(
    root: pathlib.Path, *, skip_paths: tuple[str, ...] = ()
) -> tuple[list[CallSiteIdentity], list[UnresolvedCall], list[ScanFailure]]:
    """Every candidate call site, every unresolvable form, and every unreadable file.

    `skip_paths` names path parts to exclude (the `tests` tree, for a PRODUCTION
    check), and it is named rather than assumed.

    THE THIRD LIST IS NOT DECORATION. A file that cannot be read or parsed is a
    file whose call sites are unknown, and unknown is not none: it is returned as
    a `ScanFailure` and `findings()` turns it into a failure, so a production
    module the scanner cannot read cannot silently disappear from the result.
    """
    found: list[CallSiteIdentity] = []
    unresolved: list[UnresolvedCall] = []
    failures: list[ScanFailure] = []
    root = pathlib.Path(root)
    for path in sorted(root.rglob("*.py")):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if any(part in path.parts for part in skip_paths):
            continue

        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            failures.append(
                ScanFailure(path=relative, reason=f"{type(exc).__name__}: {exc}")
            )
            continue

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
                    callee=_callee_form(node.func),
                    ast_path=_ast_path(parents, node),
                    fingerprint=_fingerprint(node, parents),
                    control_context=_control_context(parents, node),
                    proof_kwarg=_proof_kwarg(node),
                    lineno=node.lineno,
                )
            )
    return found, unresolved, failures


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
) -> dict[tuple[str, str, str, str, str, str], CallSiteIdentity]:
    """The OBSERVED mapping, keyed by identity (§7.3.13)."""
    return {identity.key: identity for identity in identities}


def findings(
    observed: list[CallSiteIdentity],
    approved: dict[tuple[str, str, str, str, str, str], CallSiteIdentity] | None,
    unresolved: list[UnresolvedCall] | None = None,
    failures: list[ScanFailure] | None = None,
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
    failures = [] if failures is None else failures
    problems: list[str] = []

    observed_map = group_by_key(observed)

    # THE INTRA-PACKAGE EXCEPTION IS BOUNDED BY UNIQUENESS, NOT BY SCOPE.
    # The triple (path, scope, entrypoint) CANNOT name a call site — a second
    # `admit(...)` in the same scope shares it — so excluding everything that
    # matches it would swallow that second call silently. The exception therefore
    # excuses AT MOST ONE matching entry on each side, and when MORE THAN ONE
    # matches, NOTHING is excused: the ambiguity is reported and every match is
    # reported with it.
    excused_observed: set = set()
    excused_unresolved: set = set()
    if exclude_intra_package_edge:
        observed_hits = [
            key for key in observed_map if (key[0], key[1], key[2]) == INTRA_PACKAGE_EDGE
        ]
        unresolved_hits = [
            index
            for index, call in enumerate(unresolved)
            if (call.path, call.scope, call.entrypoint) == INTRA_PACKAGE_EDGE
        ]
        if len(observed_hits) == 1:
            excused_observed = {observed_hits[0]}
        if len(unresolved_hits) == 1:
            excused_unresolved = {unresolved_hits[0]}
        for side, hits in (("observed", observed_hits), ("unresolved", unresolved_hits)):
            if len(hits) > 1:
                problems.append(
                    f"INTRA-PACKAGE EXCEPTION IS AMBIGUOUS: {len(hits)} {side} entries "
                    f"match the ONE excluded internal call site {INTRA_PACKAGE_EDGE}. "
                    f"The exception excuses AT MOST ONE, so NOTHING is excused here and "
                    f"every match below is reported"
                )

    for key, identity in sorted(observed_map.items()):
        if key in excused_observed:
            continue
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
    for index, call in sorted(
        enumerate(unresolved), key=lambda pair: (pair[1].path, pair[1].lineno)
    ):
        if index in excused_unresolved:
            continue
        problems.append(
            f"UNRESOLVED production call form: {call.path}:{call.lineno} "
            f"scope={call.scope} — {call.reason}. §7.3.13 makes this FAIL rather "
            f"than count as 'no call site'"
        )
    for failure in sorted(failures, key=lambda item: item.path):
        problems.append(
            f"UNREADABLE production module: {failure.path} — {failure.reason}. A "
            f"file the scan could not read has UNKNOWN call sites, and unknown is "
            f"not none; §7.3.13 makes this FAIL rather than disappear"
        )
    return problems
