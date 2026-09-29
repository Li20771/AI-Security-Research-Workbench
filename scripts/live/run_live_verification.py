"""Run opt-in live connectivity verification and write an evidence record.

Invoked by `.github/workflows/live-model-verification.yml`, which is
`workflow_dispatch` only. Not reachable from the default CI workflow, from an
ordinary pytest run, or from any hook those trigger.

    WORKBENCH_LIVE_TESTS=1 DEEPSEEK_API_KEY=... \
        python scripts/live/run_live_verification.py \
            --provider deepseek --model-ref deepseek/deepseek-flash

Exit codes:

    0  the run executed (PASS or FAIL) — the result is in the evidence record
    2  BLOCKED  — a precondition failed; no network activity occurred
    3  NOT_RUN  — the opt-in flag is absent; no network activity occurred

The distinction matters: a BLOCKED or NOT_RUN run is not a failure of the
provider, and neither is a pass. The workflow surfaces the code so the reason
is never lost behind a bare exit status.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from providers.config import example_config_path, load_provider_config  # noqa: E402
from providers.http_transport import HttpTransport  # noqa: E402
from providers.invocation import InvocationContext  # noqa: E402
from providers.live_verification import (  # noqa: E402
    LIVE_MAX_RETRIES,
    LIVE_PROVIDER_ALLOWLIST,
    LiveRunStatus,
    LiveVerifier,
)
from providers.model_registry import load_all_model_profiles  # noqa: E402
from providers.registry import load_all_providers  # noqa: E402
from providers.transport import AI02_MAX_RETRIES  # noqa: E402

EXIT_EXECUTED = 0
EXIT_BLOCKED = 2
EXIT_NOT_RUN = 3


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Opt-in live connectivity verification. Sends one fixed, minimal "
            "prompt to one allowlisted provider. Never invoked by default CI."
        )
    )
    parser.add_argument("--provider", required=True, help="provider id")
    parser.add_argument("--model-ref", required=True, help="provider_id/model_id")
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "evidence file path. Defaults to evidence/runs/<run>.yaml, which "
            "is gitignored: a run produces an artefact for review, and "
            "promotion is a separate human action."
        ),
    )
    parser.add_argument("--experiment-id", default=None)
    return parser.parse_args(argv)


def _transport_settings(provider_id: str):
    """Runtime transport settings, with the no-retry rule enforced.

    A live probe must observe one attempt, so a configuration that asked for
    retries is refused rather than silently ignored.
    """
    config = load_provider_config(example_config_path())
    settings = config.transport_for(provider_id)
    if settings.max_retries != AI02_MAX_RETRIES:
        raise SystemExit(
            f"refusing to run: max_retries is {settings.max_retries}, but live "
            f"verification requires {LIVE_MAX_RETRIES} so a failure is observed "
            "rather than retried into ambiguity (§11.4)"
        )
    return settings


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.provider not in LIVE_PROVIDER_ALLOWLIST:
        print(
            f"provider {args.provider!r} is not in the live-test allowlist "
            f"{sorted(LIVE_PROVIDER_ALLOWLIST)}"
        )

    providers = load_all_providers()
    models = load_all_model_profiles()
    settings = _transport_settings(args.provider)

    context = InvocationContext(
        providers=providers,
        models=models,
        transport=HttpTransport(),
        transport_settings_for=lambda _pid: settings,
        # The opt-in flag and the credential are read from the real process
        # environment. Without this the gate sees no opt-in and returns
        # NOT_RUN before ever reaching the credential check, which makes the
        # whole live path inert while still looking like it works.
        #
        # The resolver is the same one the offline layers use; nothing about
        # credential handling is reimplemented here.
        environ=os.environ,
    )
    verifier = LiveVerifier(context)
    record = verifier.verify(
        provider_id=args.provider,
        model_ref=args.model_ref,
        experiment_id=args.experiment_id,
    )

    output = (
        Path(args.output)
        if args.output
        else ROOT / "evidence" / "runs" / f"{record.run_id}.yaml"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(record.to_dict(), sort_keys=False), encoding="utf-8"
    )

    print(f"Live verification — {record.model_ref} @ {record.endpoint_host}")
    print(f"  status : {record.status}")
    if record.gate.code:
        print(f"  gate   : {record.gate.code} — {record.gate.detail}")
    for probe in record.probes:
        print(f"  probe  : {probe.probe_id} -> {probe.status} ({probe.observed})")
    for observation in record.observations:
        print(
            f"  capability: {observation.capability} -> {observation.outcome} "
            f"(candidate {observation.candidate_status})"
        )
    print(f"  evidence: {output}")
    print()
    print(
        "A live run produces evidence, not a grant. No profile was modified "
        "and nothing was committed (§22)."
    )

    if record.status is LiveRunStatus.NOT_RUN:
        return EXIT_NOT_RUN
    if record.status is LiveRunStatus.BLOCKED:
        return EXIT_BLOCKED
    return EXIT_EXECUTED


if __name__ == "__main__":
    raise SystemExit(main())
