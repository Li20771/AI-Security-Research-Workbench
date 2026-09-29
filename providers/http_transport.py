"""The one concrete Transport: single-shot HTTP for live verification.

AI-02-B1 deliberately shipped `Transport` as an interface with no
implementation. AI-02-B6 is the first phase that needs a real one, because a
live probe that cannot reach a provider observes nothing.

This module is **live-only**. It is imported by the live verification runner
and by nothing else: the default offline suite constructs no instance, and a
test asserts that. Nothing here is a second transport -- it is the
implementation of the interface B1 defined, using the standard library, so no
dependency is added.

Three properties matter more than the HTTP details:

**No redirects are followed.** A redirect could forward the `Authorization`
header to a host the operator never authorised. A redirect response is
returned as an error, so the credential only ever reaches the endpoint that
was configured.

**No retry.** AI-02 implements no retry loop (D-12), and a transport that
retried would multiply live-test cost while hiding the flakiness a live check
exists to observe.

**Failures are typed, never raised.** Every outcome becomes a
`TransportResult` carrying a `TransportFailureKind` and an `ErrorStage`, so the
adapter can classify it into the frozen taxonomy (§5.9).
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any

from providers.errors import ErrorStage
from providers.protocol import (
    Transport,
    TransportFailureKind,
    TransportRequest,
    TransportResult,
)

#: Refuse redirects rather than following them. Returning None makes urllib
#: surface the redirect as an HTTPError, which the caller records as a failure
#: instead of silently re-sending the request elsewhere.
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _ssl_context(verify_tls: bool) -> ssl.SSLContext:
    if verify_tls:
        return ssl.create_default_context()
    # Disabling verification is a security-relevant change requiring explicit
    # human approval (§5.11). Runtime config validation flags it; this branch
    # exists so the setting is honoured rather than silently ignored.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class HttpTransport(Transport):
    """A single-shot JSON-over-HTTP transport.

    Attributes:
        max_response_bytes: cap on a response body. A live probe expects a
            small JSON object; anything larger is a misconfigured endpoint or a
            hostile one, and reading it unbounded would be a denial-of-service
            against the probe.
    """

    def __init__(self, *, max_response_bytes: int = 256 * 1024) -> None:
        self.max_response_bytes = max_response_bytes

    def send(self, request: TransportRequest) -> TransportResult:
        body = (request.body or "").encode("utf-8")
        http_request = urllib.request.Request(
            request.url,
            data=body,
            headers=dict(request.headers),
            method=request.method,
        )

        # urllib exposes one socket-level timeout, so `timeout_total_ms` is
        # the only deadline it can honour. The connect bound is not separately
        # enforceable here, which is why `stage` is inferred from where the
        # failure occurred rather than assumed.
        timeout_seconds = max(request.timeout_total_ms / 1000.0, 0.001)
        context = _ssl_context(request.verify_tls)

        try:
            with _OPENER.open(
                http_request, timeout=timeout_seconds
            ) as response:
                return self._read(response.status, response)
        except urllib.error.HTTPError as exc:
            # A response was received; the provider answered. That is not a
            # transport failure, and the adapter classifies the status.
            return self._read(exc.code, exc)
        except ssl.SSLError as exc:
            return TransportResult.failed(
                TransportFailureKind.TRANSPORT, ErrorStage.TLS, f"TLS failure: {exc}"
            )
        except (TimeoutError, socket.timeout) as exc:
            return TransportResult.failed(
                TransportFailureKind.TIMEOUT,
                ErrorStage.RECEIVE,
                f"socket timeout: {exc}",
            )
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return TransportResult.failed(
                    TransportFailureKind.TIMEOUT,
                    ErrorStage.CONNECT,
                    f"connect timeout: {reason}",
                )
            if isinstance(reason, ssl.SSLError):
                return TransportResult.failed(
                    TransportFailureKind.TRANSPORT,
                    ErrorStage.TLS,
                    f"TLS failure: {reason}",
                )
            return TransportResult.failed(
                TransportFailureKind.TRANSPORT,
                ErrorStage.CONNECT,
                f"transport failure: {reason}",
            )
        except OSError as exc:
            return TransportResult.failed(
                TransportFailureKind.TRANSPORT, ErrorStage.CONNECT, str(exc)
            )

    def _read(self, status: int, response: Any) -> TransportResult:
        try:
            raw = response.read(self.max_response_bytes)
        except (TimeoutError, socket.timeout) as exc:
            return TransportResult.failed(
                TransportFailureKind.TIMEOUT, ErrorStage.RECEIVE, str(exc)
            )
        except OSError as exc:
            return TransportResult.failed(
                TransportFailureKind.TRANSPORT, ErrorStage.RECEIVE, str(exc)
            )

        text = raw.decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError:
            # Handed through as text. The adapter classifies a non-object
            # payload as PROTOCOL, which is the right verdict for a body that
            # is not the declared shape.
            payload = text

        return TransportResult.success(http_status=status, payload=payload)


__all__ = ["HttpTransport"]
