"""Layer 4 — live connectivity verification.

Contract §11. This is the only test module that may contact a provider, and it
is deselected from every default pytest run by `addopts = -m "not layer4"`.

Running it requires *all* of:

    pytest -m layer4                        # explicit selection
    WORKBENCH_LIVE_TESTS=1                  # explicit opt-in
    DEEPSEEK_API_KEY / MIMO_API_KEY set     # a resolvable credential

Absent any one, the probes record `BLOCKED` or `NOT_RUN` and no network
activity happens — and the assertions below check exactly that, so the
fail-closed behaviour is verified rather than assumed.

Nothing here promotes a capability. A run produces evidence; applying it to a
profile is a separate, reviewed human action (§22).
"""

from __future__ import annotations

import os

import pytest

from providers.http_transport import HttpTransport
from providers.invocation import InvocationContext
from providers.live_verification import (
    LIVE_OPT_IN_ENV,
    LIVE_OPT_IN_VALUE,
    LIVE_PROVIDER_ALLOWLIST,
    LiveBlockCode,
    LiveRunStatus,
    LiveVerifier,
)
from providers.model_registry import load_all_model_profiles
from providers.registry import load_all_providers
from providers.transport import AI02_MAX_RETRIES, TransportSettings

pytestmark = pytest.mark.layer4

DEEPSEEK_REF = "deepseek/deepseek-flash"

#: The model refs this module is willing to contact, one per provider.
LIVE_TARGETS = ("deepseek/deepseek-flash", "mimo/mimo-v2.6-pro")


def _opt_in() -> bool:
    return os.environ.get(LIVE_OPT_IN_ENV) == LIVE_OPT_IN_VALUE


def _credential_present(model_ref: str) -> bool:
    provider_id = model_ref.split("/", 1)[0]
    return bool(os.environ.get(f"{provider_id.upper()}_API_KEY", "").strip())


def _context() -> InvocationContext:
    return InvocationContext(
        providers=load_all_providers(),
        models=load_all_model_profiles(),
        transport=HttpTransport(),
        transport_settings_for=lambda _pid: TransportSettings(
            max_retries=AI02_MAX_RETRIES
        ),
        environ=os.environ,
    )


class TestRefusalsStayOffline:
    """These run whenever the module is selected, opt-in or not."""

    def test_without_opt_in_the_run_is_not_run(self):
        if _opt_in():  # pragma: no cover - depends on the operator's shell
            pytest.skip("opt-in is set; the refusal path does not apply")
        record = LiveVerifier(_context()).verify(
            provider_id="deepseek", model_ref=DEEPSEEK_REF, opt_in=None
        )
        assert record.status is LiveRunStatus.NOT_RUN
        assert record.gate.code is LiveBlockCode.OPT_IN_ABSENT
        assert record.probes == ()

    def test_an_unlisted_provider_is_blocked(self):
        record = LiveVerifier(_context()).verify(
            provider_id="openai-compatible",
            model_ref="openai-compatible/gpt",
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.BLOCKED
        assert record.gate.code is LiveBlockCode.PROVIDER_NOT_ALLOWLISTED

    def test_an_unknown_model_is_blocked(self):
        record = LiveVerifier(_context()).verify(
            provider_id="deepseek",
            model_ref="deepseek/not-a-real-model",
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.BLOCKED
        assert record.gate.code is LiveBlockCode.UNKNOWN_MODEL


@pytest.mark.parametrize("model_ref", LIVE_TARGETS)
def test_opt_in_live_probe(model_ref: str) -> None:
    """The live probe. Skips unless opted in *and* a credential resolves.

    A skip here is `NOT_RUN`, not a pass: no capability is observed, and
    nothing about this outcome supports a verification claim.
    """
    if not _opt_in():
        pytest.skip(f"{LIVE_OPT_IN_ENV} is not {LIVE_OPT_IN_VALUE}; live probe NOT_RUN")
    if not _credential_present(model_ref):
        pytest.skip(
            f"no credential resolves for {model_ref}; live probe BLOCKED. "
            "BLOCKED != PASS and supports no capability claim"
        )

    provider_id = model_ref.split("/", 1)[0]
    assert provider_id in LIVE_PROVIDER_ALLOWLIST

    record = LiveVerifier(_context()).verify(
        provider_id=provider_id, model_ref=model_ref
    )

    # The run happened. Whatever it observed is in the record, and the record
    # is the deliverable -- this assertion does not read as a capability claim.
    assert record.status in (LiveRunStatus.PASS, LiveRunStatus.FAIL, LiveRunStatus.BLOCKED)
    assert record.model_ref == model_ref
    assert record.timestamp

    # A credentialed failure is a real observation about the provider, not a
    # test failure to be retried away.
    if record.status is LiveRunStatus.PASS:
        baseline = record.probes[0]
        assert baseline.status is LiveRunStatus.PASS

        # And still: nothing is promoted. Each observation carries a candidate
        # status for a human to review.
        for observation in record.observations:
            assert observation.candidate_status.name in {
                "VERIFIED",
                "NOT_VERIFIED",
                "UNAVAILABLE",
                "UNKNOWN",
            }
