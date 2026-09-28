# Layer 3 — offline contract fixtures

Provider-shaped response bodies, checked in, used to pin normalization
behaviour across refactors. Contract §12.4.

## Provenance is mandatory

Every fixture is declared in [`manifest.yaml`](manifest.yaml) with a
provenance of exactly one of:

| Provenance | Meaning |
| --- | --- |
| `synthetic` | Hand-written to exercise a normalization path. Never a capture, never narrowed from one. |
| `scrubbed` | Derived from an observed response with any credential material removed. The scrubbing must be described in the fixture's `note`. |

**A fixture of unknown or undeclared provenance is not usable as a regression
baseline.** The loader refuses it rather than silently accepting it, because an
unlabelled payload is indistinguishable from one someone made up — and a
regression baseline that nobody can characterise is worse than none.

## A fixture is not evidence

> A fixture is not evidence of provider behaviour. Layer 3 fixtures are
> hand-written synthetic payloads or scrubbed captures. They pin *our*
> normalization logic. They never establish what a provider does, and they can
> never promote a capability to `VERIFIED`. — §12.3

Nothing here may move a capability out of `UNKNOWN`. A fixture describes what
*some* payload would normalize to; it says nothing about what either in-scope
provider actually returns. Confirming that is AI-02-B6's job, and only a dated
observation can do it.

## Constraints

- **No real credentials.** The error fixtures contain obviously synthetic
  key-shaped placeholders, because proving redaction works requires something
  to redact. They are not valid credentials and never were.
- **No network.** Fixtures are files. Nothing here is fetched.
- **No vendor material.** A vendor's documentation sample is not Workbench
  evidence and is not a fixture.
