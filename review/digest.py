"""AI-10 §6.2, §9.3 — canonical digests.

Two rules, and both matter:

```text
canonicalization   UTF-8, ensure_ascii=false, sort_keys=true, separators=(",", ":")
                   — the same rule AI-09 §19.2.1 fixed for its reference, so two
                   conforming implementations agree on the bytes.
shape              `sha256:<64 lowercase hex>` — AI-08's reference shape, so a
                   digest is a value the rest of the repository already knows how
                   to carry without mistaking it for content.
```

`default=str` is deliberately absent. A projection that contains an object
nobody projected is a programming defect, and silently stringifying it would
make the digest depend on a `repr` that no contract fixed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["canonical_json", "digest_of"]


def canonical_json(value: Any) -> str:
    """The canonical JSON text of a projection.

    Deliberately not `json.dumps` defaults: a space after a separator would make
    a digest depend on a formatting choice rather than on the value.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest_of(value: Any) -> str:
    """The `sha256:` digest of a projection's canonical JSON."""
    payload = canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
