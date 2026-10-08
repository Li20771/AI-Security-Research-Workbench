"""AI-05 §14.10, §30 step 7 — the published admission rule set (C-1).

```text
FROZEN: AI-05 owns the published admission rule set. It is exactly the six rules
        below; a seventh is an amendment to the contract (§34.1).
FROZEN: DETECTION ONLY. A rule answers "does this value match". No rule carries a
        replacement, this module holds none, and AI-05 never substitutes, redacts,
        sanitizes or normalizes a value (§14.4.1).
FROZEN: no exact-secret list and no secret registry: AI-05 holds no caller secret
        and reads no credential store.
```

### The patterns are transcribed, not imported

They are a frozen snapshot of the six credential-detection patterns the
repository's upstream sanitizer applies to provider-bound text
(`providers/redaction.py`, at main `7e7d83b74e2903f2b83e95cf35d0115d4038df90`).

Transcribed deliberately, and **never imported**. Importing that module — or its
pattern tuple — would make an upstream edit silently change what AI-05 admits,
which §14.10 forbids: changing this rule set requires an amendment. The two are
allowed to diverge, and this module is the one that decides.

### Detection, and the half that is not here

The upstream sanitizer performs two operations over these patterns: it detects a
match, and it substitutes a replacement. AI-05 performs **only the first**
(§14.4.1). There is no replacement string in this module, no `sub`, no `subn`, and
no function that returns anything but a rule or `None` — a substitution path is not
something this module forbids itself from taking; it is something it has no way to
express.

### Where the rules apply, and where they must not

The classes are **§15.2's own column**, not this module's judgement: §15.2 is the
single source of truth for field classification, and a class assigned anywhere else
is a defect in the contract. This module quotes it.

```text
Class 3   structured machine tokens — scanned (17 supplied paths)
Class 4   bounded producer-normalized text — scanned (5 supplied paths)
one admission-only supplied input — scanned, and not a §15.2 stored leaf

Class 1   NEVER scanned. A digest or a revision is a 32+ character run of
          [A-Za-z0-9_-], and C1-R06 matches exactly that: applying the rules to a
          structural field would reject every legitimate record, because a
          40-character commit SHA and a 64-character SHA-256 both match it.
Class 2   a closed-enum member; the enum is the check, and it is not scanned.
```

### Why the scan reads the supplied mapping

`check_admission_rules` reads the **supplied** values, before `EvidenceRecord`
construction (§30 step 7's ordering note). Construction derives
`references.context[].value_digest` from the supplied `value` (§12.1), and §14.6 R2
forbids computing a digest over a value that was not admitted — so the rule check
has to see that value while it is still a supplied string. The record does not keep
it afterwards: the stored form carries the digest and never the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from plugins.evidence.errors import AdmissionRuleViolation

__all__ = [
    "ADMISSION_RULES",
    "ADMISSION_ONLY_PATHS",
    "CLASS_3_PATHS",
    "CLASS_4_PATHS",
    "RULES_REVISION",
    "SCANNED_PATHS",
    "AdmissionRule",
    "check_admission_rules",
    "first_match",
]

#: Which revision of the contract published this set. Recorded as a fact about the
#: module, **not** as a field on any record: §14.10 forbids a rule-set version
#: field, because a record carrying one would invite an admission decision to
#: depend on which revision wrote it.
RULES_REVISION = "AI-05 §14.10 (Amendment 3, 2026-10-04)"


@dataclass(frozen=True, slots=True)
class AdmissionRule:
    """One published rule: an id, a name, and a pattern. **No replacement.**

    The absence of a replacement field is the point rather than an omission. A rule
    that carried one would be a rule half of which AI-05 must not use, and the
    useful thing to make impossible is carrying it at all.
    """

    #: The contract's id, e.g. `C1-R01`. Stable, and the value an error names.
    rule_id: str
    #: A descriptive name, for a reader. Never matched against and never parsed.
    name: str
    #: The frozen pattern, compiled once.
    pattern: re.Pattern[str]


#: §14.10, transcribed in the contract's order. Exactly six.
#:
#: The order matters: the FIRST matching rule is the one reported, so a value that
#: matches two rules names the earlier one and the choice is deterministic.
ADMISSION_RULES: tuple[AdmissionRule, ...] = (
    AdmissionRule(
        "C1-R01",
        "authorization header",
        re.compile(r"(?i)\bauthorization\b\s*[:=]\s*\S+"),
    ),
    AdmissionRule(
        "C1-R02",
        "credential key=value parameter",
        re.compile(
            r"(?i)\b("
            r"api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token"
            r"|bearer|token|secret|password|passwd|pwd"
            r")\b\s*[:=]\s*[\"']?([^\s\"',;}\]]+)"
        ),
    ),
    AdmissionRule(
        "C1-R03",
        "vendor sk- token",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    ),
    AdmissionRule(
        "C1-R04",
        "GitHub token prefix",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}"),
    ),
    AdmissionRule(
        "C1-R05",
        "Slack token prefix",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    ),
    AdmissionRule(
        "C1-R06",
        "long opaque token",
        re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
    ),
)

#: §14.10's Class 4 scan set: bounded producer-normalized text, in the supplied
#: form. `references.context[].value` is here rather than in a stored form because
#: the record keeps its digest and never the value.
CLASS_4_PATHS: tuple[str, ...] = (
    "provenance.actor.id",                      # §15.2 class 4, G-TEXT
    "payload.observed",                         # §15.2 class 4, G-TEXT
    "payload.reasons[]",                        # §15.2 class 4, G-TEXT
    "payload.tool_calls[].what_ran",            # §15.2 class 4, G-TEXT
    "references.supersedes[].correction_reason",  # §15.2 class 4, G-TEXT
)

#: §14.10's Class 3 scan set: structured machine tokens, in the supplied form.
#:
#: `provenance.producer` is here because **§15.2 says so**: `producer` is class 3,
#: grammar `G-REGISTERED`. The implementation additionally applies the G-TEXT shape
#: bound to it, and that does not move it — §15.2 assigns the class, and the
#: registry is its grammar. `payload.subject` is here for the same reason: §15.2
#: makes it class 3, `G-SUBJECT`.
CLASS_3_PATHS: tuple[str, ...] = (
    "provenance.producer",
    "provenance.producer_version",
    "payload.subject",
    "provenance.workspace_id",
    "provenance.experiment_id",
    "provenance.observed_at",
    "payload.binding.source_identity",
    "payload.binding.model_ref",
    "payload.binding.endpoint_host",
    "payload.reason_code",
    "references.context[].workspace_id",
    "references.context[].source_identity",
    "references.context[].subject",
    "references.decisions[].record_ref",
    "references.supersedes[].record_ref",
    "artifacts.items[].owner_workspace_id",
    "artifacts.items[].artifact_ref",
)

#: `references.context[].value` is the ONE scanned path that is **not** a §15.2
#: stored leaf. It is an admission-only supplied input: it exists only in the
#: supplied form, `ContextRef.from_mapping` derives `value_digest` from it (§12.1),
#: and the raw value is never persisted and never rendered (§12.4). It has no §15.2
#: row because it is not in a stored record at all — which is exactly why step 7
#: must read it while it is still a supplied string (R2).
ADMISSION_ONLY_PATHS: tuple[str, ...] = ("references.context[].value",)

#: Every path the rules are applied to, and the whole of the scan set. Class 1 and
#: Class 2 paths are absent, and their absence is the rule (§14.10).
SCANNED_PATHS: tuple[str, ...] = CLASS_4_PATHS + CLASS_3_PATHS + ADMISSION_ONLY_PATHS


def _values_at(raw: Mapping[str, Any], path: str) -> Iterator[Any]:
    """Every value the supplied mapping holds at `path`, in list order.

    `items[]` iterates the sequence at `items`. A key the record does not carry
    yields nothing — a supplied record holds only the fields its kind and family
    declare, and an absent field is not a value to check.

    A malformed node yields nothing rather than raising: what a value must BE is
    §30 steps 1-6's question, and this module does not answer it a second time. A
    record this walk cannot follow is refused by the step that owns its shape.
    """
    segments = path.split(".")

    def walk(node: object, remaining: tuple[str, ...]) -> Iterator[Any]:
        if not remaining:
            yield node
            return
        head, rest = remaining[0], remaining[1:]
        many = head.endswith("[]")
        key = head[:-2] if many else head
        if not isinstance(node, Mapping) or key not in node:
            return
        value = node[key]
        if not many:
            yield from walk(value, rest)
            return
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return
        for item in value:
            yield from walk(item, rest)

    yield from walk(raw, tuple(segments))


def first_match(value: str) -> AdmissionRule | None:
    """The first published rule `value` matches, or `None`.

    First, and not "the best": §14.10 fixes the order, so two rules matching one
    value is a deterministic answer rather than a choice this module makes.
    """
    for rule in ADMISSION_RULES:
        if rule.pattern.search(value):
            return rule
    return None


def check_admission_rules(raw: object) -> None:
    """§30 step 7. Refuse a supplied value that matches the published rule set.

    Raises `AdmissionRuleViolation` naming the **field path and the rule id**, or
    returns `None`. The message never carries the value, the matched text or any
    part of it: an error message is a place a value escapes to a log, and this is
    the one boundary in AI-05 where the value is the thing that must not travel.

    Nothing here is stored, modified or replaced. The record is refused whole.
    """
    if not isinstance(raw, Mapping):
        # Shape is step 1's question. A non-mapping has no fields to scan, and
        # refusing it here would be a second, disagreeing shape rule.
        return

    for path in SCANNED_PATHS:
        for value in _values_at(raw, path):
            if not isinstance(value, str):
                continue
            rule = first_match(value)
            if rule is not None:
                raise AdmissionRuleViolation(
                    f"{path} matches the published admission rule "
                    f"{rule.rule_id} ({rule.name}); §14.10 REJECTS it rather than "
                    "sanitizing it — AI-05 ships no substitution and holds none "
                    "(§14.4.1), and the producer is the layer that sanitizes"
                )
