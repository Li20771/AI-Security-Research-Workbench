"""Workbench runtime plugins.

Four plugin layers are frozen in `docs/architecture/COMPONENT_MAP.md`: Context,
Guard, Evidence, and Security Tools. **AI-03 implements Context only.** The
other three remain placeholders, and `security-tools` is not a Python package
name, so it stays a documentation directory.
"""

from __future__ import annotations

__all__: list[str] = []
