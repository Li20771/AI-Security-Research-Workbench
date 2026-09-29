"""Structural extraction of declared state from a document.

Implements AI-03 contract §7.3. A document contributes context items only
where it declares a state **structurally**. Everything else -- prose, headings,
tables, emphasis -- is ignored. There is no model in this path and no
heuristic: a line either matches the grammar or it produces nothing.

The grammar is deliberately narrow:

    ```text
    key = VALUE
    ```

* Only fenced blocks whose info string is `text` are scanned.
* `key` is at most 80 characters from `[A-Za-z0-9 ._#()/+-]`.
* `VALUE` is a whitespace- or slash-separated run of `[A-Z][A-Z0-9_]*` tokens.
* `VALUE` is recorded verbatim. It is never split, joined, or case-folded.

**Why the key character class excludes `!`, `=` and backticks.** At the AI-03-A
base SHA, `docs/AI-02_CLOSEOUT_2026-09-29.md` contains the line

    NOT_RUN != PASS

A grammar with a looser key class reads that as `key="NOT_RUN !"`,
`value="PASS"`, and manufactures a `PASS` out of a sentence asserting the
opposite. The restriction exists because a false `PASS` is the single worst
output this package could produce, and it is produced by exactly this shape of
line. `tests/context/test_declarations.py` pins the case.

**Why a compound value is not decomposed.** `BLOCKED / DEFERRED` is recorded as
`BLOCKED / DEFERRED`, and its truth state is `UNKNOWN`. Picking `BLOCKED` out of
it would be inference (D-6); keeping the compound verbatim loses nothing,
because `declared_state` carries the full text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from plugins.context.errors import DeclarationError

#: A fence delimiter, capturing the info string. A closing fence has none.
_FENCE = re.compile(r"^[ \t]*```(?P<info>[A-Za-z0-9_+-]*)[ \t]*$")

#: The only fenced block kind that is scanned (§7.3 rule 1).
_SCANNED_INFO = "text"

#: A declared-state line (§7.3 rule 2).
#:
#: The key class is the security-critical part: it admits no `!`, `=`, `<`,
#: `>`, `*` or backtick, so an inequality or an emphasised sentence cannot
#: present as a declaration.
#:
#: A value is one or more uppercase tokens joined by whitespace or a slash, so
#: `NOT STARTED` and `BLOCKED / DEFERRED` are single values. They are recorded
#: whole: splitting them would be the decomposition D-6 forbids.
_DECLARATION = re.compile(
    r"^[ \t]*(?P<key>[A-Za-z0-9][A-Za-z0-9 ._#()/+\-]{0,79}?)[ \t]*=[ \t]*"
    r"(?P<value>[A-Z][A-Z0-9_]*(?:(?:[ \t]*/[ \t]*|[ \t]+)[A-Z][A-Z0-9_]*)*)[ \t]*$"
)

#: Frozen three-entry alias table (§8.3, D-5). These are the three subjects on
#: which a document can contradict live git state, which is what makes the
#: brief's T4 conflict detectable. A larger table would start guessing at
#: prose; a smaller one would make T4 untestable.
SUBJECT_ALIASES: dict[str, str] = {
    "head": "git.head",
    "branch": "git.branch",
    "working_tree": "git.working_tree",
}


@dataclass(frozen=True, slots=True)
class Declaration:
    """One structurally declared state, before classification.

    Attributes:
        key: the declaration key, verbatim as written.
        declared_state: the value, verbatim. Never transformed.
        subject: the §8.3 subject this declaration is about.
    """

    key: str
    declared_state: str
    subject: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "declared_state": self.declared_state,
            "subject": self.subject,
        }


def fenced_text_lines(text: str) -> list[str]:
    """Lines inside ```text blocks. Everything outside them is dropped.

    Unclosed blocks are treated as running to the end of the document, which is
    how a Markdown renderer reads them; a truncated file therefore yields more
    lines rather than silently fewer.
    """
    collected: list[str] = []
    inside_text = False
    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence is not None:
            if inside_text and fence.group("info") == "":
                inside_text = False
            elif not inside_text:
                inside_text = fence.group("info") == _SCANNED_INFO
            continue
        if inside_text:
            collected.append(line)
    return collected


def normalise_key(key: str) -> str:
    """Lowercase a declaration key and collapse non-alphanumerics to `_`.

    Two documents writing `Live provider execution` and
    `live-provider-execution` must produce one subject, because a conflict
    nobody can detect is a conflict nobody can resolve (D-4).
    """
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def subject_for_declaration(key: str) -> str:
    """The §8.3 subject for a declaration key."""
    normalised = normalise_key(key)
    if not normalised:
        raise DeclarationError(f"declaration key {key!r} normalises to nothing")
    return SUBJECT_ALIASES.get(normalised, f"declared.{normalised}")


def extract_declarations(text: str) -> tuple[Declaration, ...]:
    """Every structurally declared state in a document, in document order.

    Duplicate `(subject, declared_state)` pairs are collapsed; distinct values
    for one subject are **kept**, because a document contradicting itself is a
    real disagreement and deleting half of it would hide the contradiction.
    """
    seen: set[tuple[str, str]] = set()
    found: list[Declaration] = []
    for line in fenced_text_lines(text):
        match = _DECLARATION.match(line)
        if match is None:
            continue
        subject = subject_for_declaration(match.group("key"))
        state = match.group("value")
        pair = (subject, state)
        if pair in seen:
            continue
        seen.add(pair)
        found.append(
            Declaration(
                key=match.group("key").strip(),
                declared_state=state,
                subject=subject,
            )
        )
    return tuple(found)


__all__ = [
    "SUBJECT_ALIASES",
    "Declaration",
    "extract_declarations",
    "fenced_text_lines",
    "normalise_key",
    "subject_for_declaration",
]
