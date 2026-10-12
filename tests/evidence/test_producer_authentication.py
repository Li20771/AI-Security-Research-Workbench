"""AI-05 §7.3.7 — the 22 acceptance tests the frozen contract obliges.

Contract: `docs/AI-05_EVIDENCE_EXECUTION_PLAN.md`, blob
`b89c811e9ee8da2f576b938378501c0578151dd1`, frozen as AI-05-A. The obligation
list is §7.3.7's final block, lines 1595-1671; each test below names the line of
the obligation it discharges, and **the numbering is the contract's, in the
contract's order** — nothing here is merged, split or renumbered.

WHAT THESE TESTS ARE, AND WHAT THEY ARE NOT (§7.3.7 L1670-1671)
    The contract states that no test in its list had been run and that the list
    is "obligations on the implementation, not evidence about it". This module
    supplies the assertions; it does not supply a result. `NOT_RUN` is the
    status of every test here until an execution is separately authorized and
    recorded.

THE KEY-MATERIAL RULE (§7.3.7 L1666-1669)
    Distinct keypair per producer token, the REAL verification path, and the
    configuration supplied through the SAME designated mechanism a deployment
    uses. Proofs are produced by `trust_harness` — never by a second signing
    path — and no test injects a key, a mapping or a verifier into the reader.

WHY EACH CASE DECLARES ITS CONFIGURATION
    §7.3.11's reader reads the designated variable ONCE, at module
    initialization, and §31.3's IMMUTABLE STATE rule keeps that state final for
    the process. One process therefore holds ONE configuration, so the
    acceptance suite is executed as a plan of `configuration x node id`
    invocations (started through `tests/evidence/trust_harness.py`), and each
    case asserts the outcome ITS configuration must produce. A case whose
    configuration is not the one in effect SKIPS loudly rather than asserting
    against the wrong state: the guard below compares the state a configuration
    must produce (§7.3.2's rules, read off the configuration the harness
    supplies) with the state this process actually holds, using only the
    reader's PUBLIC per-token answer.

WHY THE VARIABLE IS NOT NAMED HERE
    §31.3's ONE READER rule makes the designated variable's name appear in the
    reader and in the child-process launcher, and nowhere else; Layer 0 enforces
    that over the whole repository. This module therefore never spells it, and
    reaches the configuration only through the launcher's helpers.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import pathlib

import pytest

from plugins.evidence import AdmissionOutcome, admit, admit_to_store
from plugins.evidence.producer_auth import designated_key_for

from trust_harness import (
    PRODUCER_TOKENS,
    UNREGISTERED_TOKENS,
    proof_for,
    proof_for_record,
)

import callsite_identity
from callsite_identity import findings, group_by_key, scan_tree

pytestmark = pytest.mark.layer1

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: A fixed instant, so a digest comparison in a failure message is stable.
FIXED_CLOCK = "2026-09-30T00:00:00Z"

WS = "ws-1"
GIT_SHA = "a" * 39 + "1"

#: §7.3.8 L1685-1708 — the six codes, spelled once so a typo cannot silently
#: turn one obligation's expectation into another's.
PROOF_MISSING = "AUTHENTICATION_PROOF_MISSING"
PROOF_MALFORMED = "AUTHENTICATION_PROOF_MALFORMED"
KEY_UNAVAILABLE = "AUTHENTICATION_KEY_UNAVAILABLE"
SIGNATURE_INVALID = "AUTHENTICATION_SIGNATURE_INVALID"
INPUT_MISMATCH = "AUTHENTICATION_INPUT_MISMATCH"
INPUT_UNSERIALIZABLE = "AUTHENTICATION_INPUT_UNSERIALIZABLE"

#: §7.3.8 L1717-1730 — an unreadable producer token carries a code §30 already
#: defines, and the contract fixes WHICH one for each defect.
RECORD_MALFORMED = "RECORD_MALFORMED"
MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
FIELD_CLASS_VIOLATION = "FIELD_CLASS_VIOLATION"


# --------------------------------------------------------------------------
# the mapping under test
# --------------------------------------------------------------------------


def observation(**overrides):
    """A well-formed SOURCE_READ OBSERVATION naming producer `ai-03`.

    Its shape is the one §7.3.6 VECTOR 1 uses, with the provenance and payload
    fields §5 and §6 require for admission to reach its later stages. The
    AI-05-produced fields (`evidence_id`, the digests) are deliberately absent:
    supplying one is testing rejection, not admission.
    """
    record = {
        "schema_version": 1,
        "kind": "OBSERVATION",
        "provenance": {
            "producer": "ai-03",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-03", "type": "service"},
            "workspace_id": WS,
            "experiment_id": "EXP-20260930-0001",
            "observed_at": "2026-09-30T00:00:00Z",
        },
        "payload": {
            "family": "SOURCE_READ",
            "subject": "git.head",
            "observed": "read the live state",
            "read_status": "READ",
            "binding": {
                "source_kind": "git_current_state",
                "source_identity": "git",
                "source_revision": GIT_SHA,
            },
        },
    }
    for key, value in overrides.items():
        if value is None:
            record.pop(key, None)
        else:
            record[key] = value
    return record


def mutate(record, **changes):
    """A shallow copy of `record` with `changes` applied one level deep."""
    import copy

    out = copy.deepcopy(record)
    for key, value in changes.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def submission_for(token):
    """A well-formed submission naming `token`, in THAT TOKEN'S registered shape.

    §6.5 registers *events*, not tokens: the registry is keyed by
    (kind, family, producer_type, producer), so ai-03 is registered for
    OBSERVATION/SOURCE_READ, ai-02 for OBSERVATION/PROVIDER_PROBE, ai-04 for
    DECISION and ai-06 for EXECUTION — and a record naming ai-04 while carrying
    an OBSERVATION payload is not a registered event at all.

    The first execution exposed exactly that: obligation 8's control submitted
    every token in ai-03's shape, and ai-02/ai-04/ai-06 were refused with
    PRODUCER_NOT_REGISTERED — a §6.5 construction-stage refusal that has nothing
    to do with the key-collision rule the control exists to isolate.

    The shapes come from the repository's own well-formed builders, so the
    control submission and the collision submissions are the SAME submissions,
    which is what §7.3.7 L1639-1643 asks the control to show.
    """
    from tests.evidence.conftest import (
        make_decision,
        make_execution,
        make_provider_probe,
    )

    if token == "ai-03":
        return observation()
    if token == "ai-02":
        return make_provider_probe()
    if token == "ai-04":
        return make_decision()
    if token == "ai-06":
        return make_execution()
    raise AssertionError(
        f"{token!r} has no registered event in §6.5, so no admissible submission "
        "can be built for it; a case that needs one must say what it is testing "
        "instead of borrowing another token's shape"
    )


# --------------------------------------------------------------------------
# which configuration is in effect (public API only)
# --------------------------------------------------------------------------


def granted_tokens():
    """The tokens this process holds a designated key for (§7.3.2).

    `designated_key_for` is the reader's only public answer about the state: a
    PER-TOKEN answer that exposes neither the mapping nor the policy. That
    narrowness is why this module can check the state without naming the
    variable or reaching into the reader.
    """
    return frozenset(
        token
        for token in (*PRODUCER_TOKENS, *UNREGISTERED_TOKENS)
        if designated_key_for(token) is not None
    )


#: The state each configuration the plan uses MUST produce, read off §7.3.2's
#: rule as §7.3.7 restates it: a mapping whose key groups are all singletons, or
#: whose only duplicates are unregistered tokens under policy A, is designated;
#: every other mapping is refused WHOLE, and a refused mapping designates
#: nothing — which is indistinguishable, from outside, from an absent one.
EXPECTED_GRANTS = {
    "default": frozenset(PRODUCER_TOKENS),
    "regression": frozenset(PRODUCER_TOKENS),
    "absent": frozenset(),
    "no_entry_for_token": frozenset(
        token for token in PRODUCER_TOKENS if token != "ai-03"
    ),
    "distinct_control": frozenset((*PRODUCER_TOKENS, "ai-98", "ai-99")),
    "collision_recognized": frozenset(),
    "collision_mixed": frozenset(),
    "collision_unregistered": frozenset((*PRODUCER_TOKENS, "ai-98", "ai-99")),
    "collision_unregistered_b": frozenset(),
}


def requires(configuration):
    """Skip unless `configuration` is the one in effect.

    The plan starts this module once per configuration, selecting the node ids
    that belong to it. A run under a DIFFERENT configuration must not report
    that configuration's outcome as this one's, so it skips — visibly, with the
    two states printed — rather than passing on the wrong state.
    """
    expected = EXPECTED_GRANTS[configuration]
    observed = granted_tokens()
    if observed != expected:
        pytest.skip(
            f"{configuration} is not the configuration in effect: expected the "
            f"designated keys {sorted(expected)}, observed {sorted(observed)}. "
            "Run this node through tests/evidence/trust_harness.py with the "
            f"configuration {configuration!r} (see the module docstring)."
        )


def outcome_of(result):
    return result.outcome


def reason_of(result):
    return result.reason_code


# --------------------------------------------------------------------------
# obligation 1 — a valid proof and an accepted producer claim (§7.3.7 L1598)
# --------------------------------------------------------------------------


class TestObligation01ValidProofAccepted:
    """§7.3.7 L1598. The positive control: without it, a refusal proves nothing."""

    def test_obligation_01_valid_proof_is_accepted(self):
        requires("regression")
        raw = observation()
        result = admit(
            raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
        )
        assert outcome_of(result) is AdmissionOutcome.ACCEPTED, (
            "a well-formed claim signed by the token it names, under a mapping "
            f"with one key per registered token, must be ACCEPTED; got "
            f"{outcome_of(result)} / {reason_of(result)}"
        )
        assert result.record is not None, "an ACCEPTED admission carries a record"
        assert not str(reason_of(result)).startswith("AUTHENTICATION_")


# --------------------------------------------------------------------------
# obligations 2-8 — the mapping, its collisions, and its fail-closed paths
# --------------------------------------------------------------------------


class TestObligation02NoProofAndNoMapping:
    """§7.3.7 L1599. Two DIFFERENT states, and §7.3.8 keeps them distinguishable."""

    def test_obligation_02a_no_proof_and_no_mapping(self):
        requires("absent")
        result = admit(observation(), clock=lambda: FIXED_CLOCK)
        assert outcome_of(result) is AdmissionOutcome.REJECTED
        assert reason_of(result) == PROOF_MISSING, (
            "an omitted proof is AUTHENTICATION_PROOF_MISSING rather than a "
            f"TypeError or a key complaint; got {reason_of(result)}"
        )

    def test_obligation_02b_proof_but_no_mapping(self):
        requires("absent")
        raw = observation()
        result = admit(
            raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED
        assert reason_of(result) == KEY_UNAVAILABLE, (
            "with no designated mapping the proof cannot be checked, and the "
            "code says so rather than blaming the proof; got "
            f"{reason_of(result)}"
        )


class TestObligation03NoEntryForToken:
    """§7.3.7 L1600."""

    def test_obligation_03_no_entry_for_claimed_token(self):
        requires("no_entry_for_token")
        raw = observation()  # names ai-03, which this mapping has no entry for
        result = admit(
            raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED
        assert reason_of(result) == KEY_UNAVAILABLE, (
            f"got {reason_of(result)}; §7.3.8 defines this state as "
            "AUTHENTICATION_KEY_UNAVAILABLE"
        )


class TestObligation04RecognizedCollision:
    """§7.3.7 L1601-1607. ONE key, TWO REGISTERED tokens, and every submission."""

    def test_obligation_04_recognized_collision_refuses_every_submission(self):
        requires("collision_recognized")
        failures = []
        for token in PRODUCER_TOKENS:
            raw = submission_for(token)
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is not AdmissionOutcome.REJECTED or (
                reason_of(result) != KEY_UNAVAILABLE
            ):
                failures.append((token, outcome_of(result), reason_of(result)))
        assert not failures, (
            "the mapping is refused WHOLE, so a submission naming a token whose "
            "entry was not part of the collision is refused too (§7.3.7 "
            f"L1605-1607); these were not: {failures}"
        )


class TestObligation05MixedCollision:
    """§7.3.7 L1608-1617. A registered token sharing a key with an unregistered one."""

    def test_obligation_05_mixed_collision_refuses_under_either_policy(self):
        requires("collision_mixed")
        failures = []
        for token in PRODUCER_TOKENS:
            raw = submission_for(token)
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is not AdmissionOutcome.REJECTED or (
                reason_of(result) != KEY_UNAVAILABLE
            ):
                failures.append((token, outcome_of(result), reason_of(result)))
        assert not failures, (
            "§7.3.7 L1608-1617 requires the SAME outcome as the recognized "
            "collision: the whole mapping refused, every submission refused "
            "with AUTHENTICATION_KEY_UNAVAILABLE, and a test that accepted this "
            f"shape under POLICY A would be wrong. Rejections missing: {failures}"
        )


class TestObligation06UnregisteredOnlyCollision:
    """§7.3.7 L1618-1633. The ONE case §7.3.2 lets the two policies differ on.

    EITHER policy satisfies the contract, so the assertion is written against
    what BOTH require — never accepted, no §6.5 identity, and a consistent
    reader — and the policy-specific half is asserted only for the state this
    run actually holds. A criterion that named one policy as the only compliant
    answer would fail a compliant deployment that chose the other.
    """

    def test_obligation_06a_policy_a_tolerates_the_mapping_but_never_admits(self):
        requires("collision_unregistered")
        failures = []
        for token in (*UNREGISTERED_TOKENS, PRODUCER_TOKENS[0]):
            raw = mutate(
                observation(),
                provenance=mutate(
                    observation()["provenance"], producer=token, actor={
                        "id": token, "type": "service"
                    },
                ),
            )
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is AdmissionOutcome.ACCEPTED:
                failures.append((token, reason_of(result)))
        assert not failures, (
            "under POLICY A the mapping stays usable, so a signature over such "
            "a token's claim MAY VERIFY — and §6.6 MUST then refuse the record "
            "during construction. No submission naming such a token may be "
            f"ACCEPTED. Accepted: {failures}"
        )

    def test_obligation_06b_policy_b_refuses_over_all_entries(self):
        requires("collision_unregistered_b")
        failures = []
        for token in (*UNREGISTERED_TOKENS, PRODUCER_TOKENS[0]):
            raw = mutate(
                observation(),
                provenance=mutate(
                    observation()["provenance"], producer=token, actor={
                        "id": token, "type": "service"
                    },
                ),
            )
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is not AdmissionOutcome.REJECTED or (
                reason_of(result) != KEY_UNAVAILABLE
            ):
                failures.append((token, outcome_of(result), reason_of(result)))
        assert not failures, (
            "under POLICY B the mapping is refused over ALL entries, so every "
            "submission is refused with AUTHENTICATION_KEY_UNAVAILABLE and no "
            f"signature verification and no construction occurs. Got: {failures}"
        )

    def test_obligation_06c_reader_is_consistent(self):
        """§7.3.7 L1630-1633 — never a mixture, under either policy.

        The state must be EXACTLY one of the two the contract permits: the whole
        tolerated group present, or nothing designated. A state holding only part
        of the group is the mixture the contract forbids — a reader that trimmed
        the colliding pair would leave the surviving entries authenticating as
        though the collision had never existed (L1636-1638).

        The reader's public answer cannot, by design, distinguish "this run is
        not one of the two collision configurations" from "the mapping was
        trimmed", so a failure here names BOTH possibilities and points at the
        recorded configuration for the run. That is why the execution plan
        records `configuration x node id`: the run record is what says which
        configuration this node was started under.
        """
        granted = granted_tokens()
        tolerated = EXPECTED_GRANTS["collision_unregistered"]
        refused = EXPECTED_GRANTS["collision_unregistered_b"]
        assert granted in (tolerated, refused), (
            "the reader must refuse EVERY duplicate of a kind or tolerate EVERY "
            "duplicate of that kind, never a mixture. Observed "
            f"{sorted(granted)}, which is neither the tolerated group "
            f"{sorted(tolerated)} nor nothing {sorted(refused)} — either the "
            "mapping was trimmed, or this node was started under a different "
            "configuration than the run record claims"
        )


class TestObligation07WholeMappingRefused:
    """§7.3.7 L1634-1638. No subset, no first-or-last entry, no warning-and-continue."""

    def test_obligation_07_a_surviving_duplicate_never_authenticates(self):
        requires("collision_unregistered")
        # ai-02's entry is NOT part of the collision. Under POLICY A the mapping
        # survives, so ai-02's key must be present — which is exactly what makes
        # this a test of "the mapping was not trimmed", not of "nothing is
        # designated". Under a trimming reader ai-98/ai-99 would vanish and the
        # remaining entries would authenticate as though the collision had never
        # existed; §7.3.7 L1636-1638 names that outcome.
        granted = granted_tokens()
        assert "ai-98" in granted and "ai-99" in granted, (
            "a reader that trimmed the mapping would leave its surviving "
            "entries authenticating as though the collision had never existed; "
            f"the tolerated group must be intact. Observed: {sorted(granted)}"
        )

    def test_obligation_07_a_refusing_reader_designates_nothing(self):
        requires("collision_recognized")
        assert granted_tokens() == frozenset(), (
            "a refused mapping designates no key at all — not a subset, not a "
            "first or last entry. Observed: " + repr(sorted(granted_tokens()))
        )


class TestObligation08DistinctKeysControl:
    """§7.3.7 L1639-1643. The control that shows the three tests above test the
    collision rule and not merely the absence of a mapping."""

    def test_obligation_08_distinct_keys_control_admits(self):
        requires("distinct_control")
        failures = []
        for token in PRODUCER_TOKENS:
            raw = submission_for(token)
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is not AdmissionOutcome.ACCEPTED:
                failures.append((token, reason_of(result)))
            elif result.record is None:
                failures.append((token, "ACCEPTED without a record"))
        assert not failures, (
            "with distinct key material for every entry, the submissions that "
            "failed under a collision must succeed — the complete result, not an "
            "intermediate state; otherwise the collision tests were only testing "
            f"the absence of a mapping. Failed: {failures}"
        )


# --------------------------------------------------------------------------
# obligations 9-13 — the envelope, the signature, and the signed input
# --------------------------------------------------------------------------


def proof_with(message_bytes, signature_hex):
    return {
        "message_b64u": base64.urlsafe_b64encode(message_bytes)
        .rstrip(b"=")
        .decode("ascii"),
        "signature": signature_hex,
    }


class TestObligation09MalformedEnvelope:
    """§7.3.7 L1644-1645. Three defects, one code."""

    def test_obligation_09a_non_base64url_character(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        broken = dict(good, message_b64u=good["message_b64u"][:-1] + "!")
        result = admit(raw, producer_proof=broken, clock=lambda: FIXED_CLOCK)
        assert reason_of(result) == PROOF_MALFORMED, reason_of(result)

    def test_obligation_09b_padding(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        broken = dict(good, message_b64u=good["message_b64u"] + "=")
        result = admit(raw, producer_proof=broken, clock=lambda: FIXED_CLOCK)
        assert reason_of(result) == PROOF_MALFORMED, reason_of(result)

    def test_obligation_09c_non_canonical_encoding(self):
        """A Base64url string whose final quantum carries UNUSED BITS set.

        §7.3.3 refuses it as malformed rather than accepting it as an alias of a
        valid value. Whether such an alias exists is a property of the MESSAGE
        BYTES, not of the string: base64 encodes three bytes per four characters,
        so a final quantum carrying unused bits exists only when
        len(bytes) % 3 != 0. The submission is therefore CHOSEN so that its
        signed input has such a quantum, instead of hoping an arbitrary one does
        (the first execution skipped for exactly that reason).

        Everything else is kept valid — the mapping is the one that was signed,
        the signature is genuine and the envelope is otherwise well formed — so
        the ONLY defect in the submission is the encoding.
        """
        requires("regression")
        from plugins.evidence.signed_input import signed_input

        raw = None
        message = None
        good = None
        for pad in range(0, 8):
            candidate = observation(
                payload=dict(
                    observation()["payload"],
                    observed="read the live state" + "x" * pad,
                )
            )
            candidate_message = signed_input(candidate)
            if len(candidate_message) % 3 == 0:
                continue  # a whole final quantum: no unused bits to set
            raw = candidate
            message = candidate_message
            good = proof_for_record(candidate)
            break
        assert message is not None, (
            "no candidate submission produced a signed input with a partial "
            "final quantum, so this case could not be constructed — a test "
            "defect, not a contract result"
        )
        body = good["message_b64u"]
        assert base64.urlsafe_b64decode(
            body + "=" * (-len(body) % 4)
        ) == message, "the proof's message_b64u must encode that signed input"

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last = alphabet.index(body[-1])
        aliased = None
        for bump in range(1, 16):
            if last + bump >= len(alphabet):
                break
            candidate = body[:-1] + alphabet[last + bump]
            if base64.urlsafe_b64decode(
                candidate + "=" * (-len(candidate) % 4)
            ) == message:
                aliased = candidate
                break
        assert aliased is not None, (
            "a submission with a partial final quantum must have an alias that "
            "decodes to the same bytes; none was found, so the construction is "
            "wrong"
        )
        assert aliased != body
        result = admit(
            raw, producer_proof=dict(good, message_b64u=aliased),
            clock=lambda: FIXED_CLOCK,
        )
        assert reason_of(result) == PROOF_MALFORMED, (
            "a NON-CANONICAL encoding whose final quantum carries unused bits "
            f"is refused as malformed, not accepted as an alias; got {reason_of(result)}"
        )

    def test_obligation_09d_signature_is_not_lowercase_hex_128(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        for broken_signature in (
            good["signature"].upper(),
            good["signature"][:-1],
            good["signature"] + "0",
        ):
            result = admit(
                raw,
                producer_proof=dict(good, signature=broken_signature),
                clock=lambda: FIXED_CLOCK,
            )
            assert reason_of(result) == PROOF_MALFORMED, (
                f"signature {broken_signature[:12]}… gave {reason_of(result)}"
            )


class TestObligation10SignatureDoesNotVerify:
    """§7.3.7 L1646."""

    def test_obligation_10_signature_does_not_verify(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        flipped = ("0" if good["signature"][0] != "0" else "1") + good["signature"][1:]
        result = admit(
            raw, producer_proof=dict(good, signature=flipped), clock=lambda: FIXED_CLOCK
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED
        assert reason_of(result) == SIGNATURE_INVALID, reason_of(result)


class TestObligation11CrossProducer:
    """§7.3.7 L1647. Another token's private key."""

    def test_obligation_11_cross_producer_key_is_refused(self):
        requires("regression")
        raw = observation()  # names ai-03
        result = admit(
            raw,
            producer_proof=proof_for("ai-04", raw),
            clock=lambda: FIXED_CLOCK,
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED
        assert reason_of(result) == SIGNATURE_INVALID, (
            "V4 verifies under the designated key for the CLAIMED token, so a "
            "signature made with another token's private key does not verify; "
            f"got {reason_of(result)}"
        )


class TestObligation12Replay:
    """§7.3.7 L1648-1649. A proof replayed against a changed signed input.

    WHICH code applies follows from §7.3.5's stated order — V4 (verify) runs
    before V5 (compare), §7.3.6 L1400-1404 — and from V3 (key selection) running
    first of all. A mutation that changes which KEY applies is refused at V4 or
    V3; a mutation that leaves the key alone can only be caught by V5.

    STEP 7 IS CHECKED FIRST, AND THESE FOUR MUTATIONS DO NOT TRIP IT. §14.10's
    rule set is six credential patterns applied to a fixed scanned-path set
    (`payload.subject` and `provenance.workspace_id` are in it; `payload.family`
    and `kind` are not), and none of the four mutated values matches a pattern —
    so the rule set passes, authentication runs, and V5 is the step that refuses.
    A mutation that DID trip a rule would be refused there instead, which is why
    12a reports a step-7 code as a test defect rather than a contract result.
    """

    def test_obligation_12a_payload_kind_family_workspace_mutations(self):
        requires("regression")
        base = observation()
        good = proof_for_record(base)
        cases = {
            "kind": mutate(base, kind="DECISION"),
            "family": mutate(
                base, payload=mutate(base["payload"], family="PROVIDER_PROBE")
            ),
            "workspace": mutate(
                base,
                provenance=mutate(base["provenance"], workspace_id="ws-2"),
            ),
            "payload": mutate(
                base, payload=mutate(base["payload"], subject="git.branch")
            ),
        }
        failures = []
        for name, mutated in cases.items():
            result = admit(mutated, producer_proof=good, clock=lambda: FIXED_CLOCK)
            if reason_of(result) != INPUT_MISMATCH:
                failures.append((name, outcome_of(result), reason_of(result)))
        assert not failures, (
            "the decoded carried message is not the signed input reconstructed "
            "from the submitted mapping, so V5 must refuse it with "
            "AUTHENTICATION_INPUT_MISMATCH. (A step 7 rule firing first would "
            "mean the mutation tripped a published rule, which is a test defect, "
            f"not a contract result.) Got: {failures}"
        )

    def test_obligation_12b_producer_mutation_to_another_registered_token(self):
        requires("regression")
        base = observation()
        good = proof_for_record(base)
        mutated = mutate(
            base,
            provenance=mutate(
                base["provenance"],
                producer="ai-04",
                actor={"id": "ai-04", "type": "service"},
            ),
        )
        result = admit(mutated, producer_proof=good, clock=lambda: FIXED_CLOCK)
        assert reason_of(result) == SIGNATURE_INVALID, (
            "naming another REGISTERED token changes which key V3 selects, so the "
            "unchanged signature is refused at V4 before V5 can compare; got "
            f"{reason_of(result)}"
        )

    def test_obligation_12c_producer_mutation_to_an_unregistered_token(self):
        requires("regression")
        base = observation()
        good = proof_for_record(base)
        mutated = mutate(
            base,
            provenance=mutate(
                base["provenance"],
                producer="ai-98",
                actor={"id": "ai-98", "type": "service"},
            ),
        )
        result = admit(mutated, producer_proof=good, clock=lambda: FIXED_CLOCK)
        assert reason_of(result) == KEY_UNAVAILABLE, (
            "the mapping holds no key for an unregistered token, so V3 refuses "
            f"before any signature is checked; got {reason_of(result)}"
        )


class TestObligation13Unserializable:
    """§7.3.7 L1650-1651. No canonical serialization exists at all — which §7.3.8
    L1702-1708 keeps DISTINCT from "bytes exist and differ"."""

    def test_obligation_13a_out_of_domain_value(self):
        requires("regression")
        base = observation()
        # The proof is made over the WELL-FORMED base, not over the mutated
        # mapping: `proof_for_record` serializes its argument, so asking it to
        # sign an unserializable mapping would raise AuthenticationInputUnserializable
        # inside the TEST, before admission was ever reached. What this case
        # exercises is a producer that submits a mapping the verifier cannot
        # serialize, carrying a signature that is valid over other bytes: V1-V4
        # pass and V5 has no bytes to compare, which is the state §7.3.8
        # L1702-1708 keeps DISTINCT from a mismatch.
        good = proof_for_record(base)
        for out_of_domain in (1.5, b"bytes", {1, 2}):
            mutated = mutate(
                base, payload=mutate(base["payload"], observed=out_of_domain)
            )
            result = admit(
                mutated,
                producer_proof=good,
                clock=lambda: FIXED_CLOCK,
            )
            assert reason_of(result) == INPUT_UNSERIALIZABLE, (
                f"{type(out_of_domain).__name__} is out of AI-05-CJ-1's domain; "
                f"got {reason_of(result)}"
            )

    def test_obligation_13b_unpaired_surrogate(self):
        requires("regression")
        base = observation()
        mutated = mutate(
            base, payload=mutate(base["payload"], subject="lone\ud800surrogate")
        )
        # Signed over the base for the same reason as 13a: the surrogate is what
        # V5 cannot serialize, and signing the mutated mapping would raise here.
        good = proof_for_record(base)
        result = admit(
            mutated, producer_proof=good, clock=lambda: FIXED_CLOCK
        )
        assert reason_of(result) == INPUT_UNSERIALIZABLE, (
            "rule 9 refuses a string carrying an unpaired surrogate because rule "
            f"5 cannot be applied to it; got {reason_of(result)}"
        )


# --------------------------------------------------------------------------
# obligation 14 — an unreadable producer token (§7.3.7 L1652-1653)
# --------------------------------------------------------------------------


class TestObligation14UnreadableToken:
    """§7.3.7 L1652-1653, with §7.3.8 L1717-1736.

    Two things are owed: an EXISTING shape reason for each defect, and evidence
    that NO key lookup, NO decoding and NO signature verification occurred.

    The first half is a runtime assertion below. The second half CANNOT be a
    runtime assertion here: the reader exposes a per-token key answer and
    nothing else (§31.3 keeps the mapping private), so no in-process observation
    distinguishes "refused before the lookup" from "refused after it" without
    either mutating the reader's state or wrapping the real path — both of which
    §31.3 and §7.3.7's bypass prohibition forbid. What this module CAN do, and
    does, is assert the ORDER IN THE SOURCE: the shape read precedes the key
    selection, and the key selection precedes decoding and verification. That is
    a source-level control-flow assertion, not a runtime proof, and it is
    reported as such.
    """

    def test_obligation_14a_existing_shape_reason_for_each_defect(self):
        requires("regression")
        base = observation()
        cases = {
            # §7.3.8 L1724 — the supplied value is not a mapping
            "not_a_mapping": ("RECORD_MALFORMED", ["not", "a", "mapping"]),
            # L1725 — provenance is ABSENT, and null is the other spelling of the
            # same row. `mutate` drops a None, so the null cases are built by
            # setting the key explicitly; the two are different inputs and the
            # contract puts them in one row.
            "provenance_absent": ("MISSING_REQUIRED_FIELD", mutate(base, provenance=None)),
            "provenance_null": ("MISSING_REQUIRED_FIELD", dict(base, provenance=None)),
            # L1726 — provenance is not an object
            "provenance_not_object": ("RECORD_MALFORMED", mutate(base, provenance="x")),
            # L1727 — provenance.producer is ABSENT, and null
            "producer_absent": (
                "MISSING_REQUIRED_FIELD",
                mutate(base, provenance=mutate(base["provenance"], producer=None)),
            ),
            "producer_null": (
                "MISSING_REQUIRED_FIELD",
                mutate(base, provenance=dict(base["provenance"], producer=None)),
            ),
            # L1728-1730 — producer is not a string, is empty, or is not the
            # bounded text §7 requires
            "producer_not_string": (
                "FIELD_CLASS_VIOLATION",
                mutate(base, provenance=mutate(base["provenance"], producer=7)),
            ),
            "producer_empty": (
                "FIELD_CLASS_VIOLATION",
                mutate(base, provenance=mutate(base["provenance"], producer="")),
            ),
        }
        # V1 runs before V2 (the ordering 14c asserts), so a case that omitted
        # the proof would be refused at the ENVELOPE with
        # AUTHENTICATION_PROOF_MISSING and V2 would never run. Every case carries
        # a well-formed proof, so the shape read is what fails.
        good = proof_for_record(base)
        failures = []
        for name, (expected, raw) in cases.items():
            result = admit(raw, producer_proof=good, clock=lambda: FIXED_CLOCK)
            if reason_of(result) != expected:
                failures.append((name, expected, outcome_of(result), reason_of(result)))
        assert not failures, (
            "V2's failure carries the reason the corresponding construction-time "
            "check would carry (§7.3.8 L1720-1722); a NEW authentication code "
            "here would be a second, disagreeing shape vocabulary. "
            f"Mismatches (case, expected, outcome, actual): {failures}"
        )

    def test_obligation_14b_no_authentication_code_is_used_for_a_shape_defect(self):
        requires("regression")
        base = observation()
        result = admit(
            mutate(base, provenance=mutate(base["provenance"], producer=None)),
            producer_proof=proof_for_record(base),
            clock=lambda: FIXED_CLOCK,
        )
        assert not str(reason_of(result)).startswith("AUTHENTICATION_"), (
            "an unreadable producer token is NOT an authentication failure and "
            f"gets no code of its own (§7.3.8 L1717-1719); got {reason_of(result)}"
        )

    def test_obligation_14c_shape_read_precedes_key_selection_decoding_verification(self):
        """The control-flow half, asserted over the reader's own source.

        §7.3.5 fixes V1 → V2 → V3 → V4, and §7.3.8 L1732-1733 states that on an
        unreadable-token path there is "NO key lookup, NO decoding and NO
        signature verification". This asserts that ORDER IN THE SOURCE, which is
        the only place it can be observed: §31.3's immutable-state rule forbids
        instrumenting the reader, and wrapping the real path would be the
        test-only bypass §7.3.7 forbids.

        EFFECTS, NOT CALL NAMES, AND TRANSITIVELY. A key lookup, a decode and a
        verification are looked for as EFFECTS. An effect performed inside a
        module-local helper is attributed to the helper's CALL SITE, and each
        function's effect set is closed transitively over the module-local calls
        it makes — so extracting a key lookup into a helper does NOT move it out
        of this assertion's reach. Nothing is concluded from a helper's name.
        (A membership test such as `token in state.keys` is deliberately NOT
        counted: it looks up no key, and counting every `keys` attribute would
        flag an ordinary mapping's `.keys()` and fail a compliant reader.)

        IT FAILS WHEN IT CANNOT PROVE. If the envelope step, the shape read, or
        any of the three effect classes cannot be identified, this test FAILS
        with "cannot prove". A shape read moved into a helper, a renamed step, or
        any other unrecognised structure is reported — never tolerated silently.
        """
        source_path = REPO_ROOT / "plugins" / "evidence" / "producer_auth.py"
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"), filename=str(source_path)
        )

        def resolved_name(node):
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                return node.attr
            return None

        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        envelope_name = "_envelope"
        shape_read_name = "_claimed_producer"
        decode_names = {"_decode_message"}
        verify_names = {"_verify"}
        key_lookup_name = "designated_key_for"
        key_attribute = "keys"

        def direct_effects(function):
            """(effects performed here, module-local names this body calls)."""
            found = set()
            calls = set()
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    name = resolved_name(node.func)
                    if name in decode_names:
                        found.add("decode")
                    elif name in verify_names:
                        found.add("verify")
                    elif name == key_lookup_name:
                        found.add("key")
                    elif (
                        name in ("get", "pop", "setdefault")
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == key_attribute
                    ):
                        found.add("key")  # e.g. `state.keys.get(token)`
                    elif name is not None:
                        calls.add(name)
                elif (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == key_attribute
                ):
                    found.add("key")  # e.g. `state.keys[token]`
            return found, calls

        effects = {}
        callers = {}
        for name, function in functions.items():
            found, calls = direct_effects(function)
            effects[name] = set(found)
            callers[name] = calls
        changed = True
        while changed:  # transitive closure over module-local calls
            changed = False
            for name, calls in callers.items():
                for called in calls:
                    if called in effects and not effects[called] <= effects[name]:
                        effects[name] |= effects[called]
                        changed = True

        authenticate = functions.get("authenticate")
        assert authenticate is not None, (
            "cannot prove the order: producer_auth.authenticate, the entry point "
            "§7.3.5's V1-V5 run in, was not found"
        )

        positions = {}
        sites = []
        for node in ast.walk(authenticate):
            if isinstance(node, ast.Call):
                name = resolved_name(node.func)
                if name in (envelope_name, shape_read_name) and name not in positions:
                    positions[name] = node.lineno
                if name in decode_names:
                    sites.append(("decode", node.lineno))
                if name in verify_names:
                    sites.append(("verify", node.lineno))
                if name == key_lookup_name:
                    sites.append(("key", node.lineno))
                if (
                    name in ("get", "pop", "setdefault")
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == key_attribute
                ):
                    sites.append(("key", node.lineno))
                if name is not None and name in effects:
                    for effect in sorted(effects[name]):
                        sites.append((effect, node.lineno))
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == key_attribute
            ):
                sites.append(("key", node.lineno))

        missing = [
            step
            for step in (envelope_name, shape_read_name)
            if step not in positions
        ]
        assert not missing, (
            "cannot prove the order: these steps are not called from "
            f"authenticate: {missing}. A shape read that has been moved into a "
            "helper cannot be followed by this assertion, so it is reported as "
            "unprovable rather than accepted"
        )
        envelope = positions[envelope_name]
        shape_read = positions[shape_read_name]
        assert envelope < shape_read, (
            "§7.3.5 runs V1 before V2: the envelope is validated before the "
            f"claimed producer is read (envelope at line {envelope}, shape read "
            f"at line {shape_read})"
        )

        for effect, description in (
            ("key", "a key lookup"),
            ("decode", "message decoding"),
            ("verify", "signature verification"),
        ):
            lines = sorted(line for kind, line in sites if kind == effect)
            assert lines, (
                f"cannot prove the order: no {description} could be identified in "
                "authenticate, directly or through a module-local helper. The "
                "guarantee that none precedes a readable producer token is "
                "therefore UNPROVEN here, not satisfied"
            )
            assert shape_read < lines[0], (
                f"§7.3.8 L1732-1733 forbids {description} on the unreadable-token "
                f"paths: the shape read is at line {shape_read} but the earliest "
                f"{description} is at line {lines[0]}"
            )


# --------------------------------------------------------------------------
# obligation 15 — the proof omitted and passed as None, at BOTH entry points
# --------------------------------------------------------------------------


class TestObligation15ProofMissingAtBothEntryPoints:
    """§7.3.7 L1654-1655. REJECTED, never a TypeError."""

    def test_obligation_15a_admit_omitted_and_none(self):
        requires("regression")
        raw = observation()
        for label, call in (
            ("omitted", lambda: admit(raw, clock=lambda: FIXED_CLOCK)),
            ("none", lambda: admit(raw, producer_proof=None, clock=lambda: FIXED_CLOCK)),
        ):
            try:
                result = call()
            except TypeError as exc:  # the failure this obligation forbids
                pytest.fail(
                    f"admit() with the proof {label} raised TypeError({exc}); "
                    "§7.3.3 makes a missing proof an admission RESULT, and §7.3.8 "
                    "L1685-1686 names its code"
                )
            assert outcome_of(result) is AdmissionOutcome.REJECTED, f"{label}: {outcome_of(result)}"
            assert reason_of(result) == PROOF_MISSING, f"{label}: {reason_of(result)}"

    def test_obligation_15b_admit_to_store_omitted_and_none(self):
        requires("regression")
        raw = observation()
        for label, proof in (("omitted", ...), ("none", None)):
            store = Ledger()
            kwargs = {} if proof is ... else {"producer_proof": proof}
            try:
                result = admit_to_store(
                    raw, store=store, clock=lambda: FIXED_CLOCK, **kwargs
                )
            except TypeError as exc:
                pytest.fail(
                    f"admit_to_store() with the proof {label} raised TypeError({exc}); "
                    "§7.3.3 makes a missing proof an admission RESULT"
                )
            assert outcome_of(result) is AdmissionOutcome.REJECTED, f"{label}: {outcome_of(result)}"
            assert reason_of(result) == PROOF_MISSING, f"{label}: {reason_of(result)}"
            assert store.calls == [], (
                f"{label}: a REJECTED admission must not touch the store; "
                f"observed {store.calls}"
            )


# --------------------------------------------------------------------------
# obligation 16 — an unknown or malformed field (§7.3.7 L1656)
# --------------------------------------------------------------------------


class TestObligation16UnknownOrMalformedField:
    """§7.3.7 L1656. The record is refused by a rule that is not authentication's."""

    def test_obligation_16_unknown_and_malformed_fields(self):
        requires("regression")
        base = observation()
        cases = {
            "unknown_member": mutate(base, unexpected_member="x"),
            "malformed_kind": mutate(base, kind=17),
        }
        failures = []
        for name, raw in cases.items():
            # The proof is made over the SUBMITTED mapping, so authentication
            # SUCCEEDS and the record reaches the check that owns its shape. A
            # proof over the unmutated base would make V5 fire first with
            # AUTHENTICATION_INPUT_MISMATCH and this test would be measuring the
            # replay rule instead of the shape rule.
            result = admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            )
            if outcome_of(result) is not AdmissionOutcome.REJECTED:
                failures.append((name, outcome_of(result), reason_of(result)))
            elif str(reason_of(result)).startswith("AUTHENTICATION_"):
                failures.append((name, "authentication code", reason_of(result)))
        assert not failures, (
            "an unknown or malformed field is refused by the record's own rules, "
            "with that rule's reason code — an authentication code here would mean "
            f"step 7b ran before the rule set. Got: {failures}"
        )


# --------------------------------------------------------------------------
# obligation 17 — rejection without persistence and without store contact
# --------------------------------------------------------------------------


class Ledger:
    """A store that RECORDS every interaction, so "zero" is a count and not a
    reading of the return value.

    It offers `write` deliberately: `admit_to_store` refuses a store without one
    by raising TypeError (§20.3), and that refusal is about the store's shape,
    not about the submission — conflating the two would hide the property this
    obligation is about.
    """

    def __init__(self):
        self.calls = []

    def contains(self, evidence_id):
        self.calls.append(("contains", evidence_id))
        return False

    def write(self, record):
        self.calls.append(("write", getattr(record, "evidence_id", None)))
        return None


class TestObligation17RejectionTouchesNoStore:
    """§7.3.7 L1657-1658 and §7.3.8 L1755-1758."""

    def test_obligation_17a_admit_to_store_rejects_without_contact(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        flipped = ("0" if good["signature"][0] != "0" else "1") + good["signature"][1:]
        store = Ledger()
        result = admit_to_store(
            raw,
            store=store,
            producer_proof=dict(good, signature=flipped),
            clock=lambda: FIXED_CLOCK,
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED, (
            "an authentication failure must produce the contract's REJECTED "
            f"result; got {outcome_of(result)} / {reason_of(result)}"
        )
        assert reason_of(result) == SIGNATURE_INVALID, reason_of(result)
        assert store.calls == [], (
            "the store must not be contacted on a non-ACCEPTED path — not "
            f"`contains`, not `write`; observed {store.calls}"
        )

    def test_obligation_17b_admit_rejects_an_authentication_failure(self):
        """The other entry point, on an AUTHENTICATION failure.

        `admit` takes no store — §7.3.8 L1755-1758 says the property is a
        property of the entry point — so there is no store interaction to count
        here and inventing one would assert something the contract does not
        require. What is required at this entry point is that the authentication
        failure produces the contract's REJECTED result rather than an exception
        or no result at all.
        """
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        try:
            result = admit(
                raw,
                producer_proof=dict(good, signature="0" * 128),
                clock=lambda: FIXED_CLOCK,
            )
        except Exception as exc:  # noqa: BLE001 - the state this obligation forbids
            pytest.fail(
                f"admit() raised {type(exc).__name__}({exc}) on an authentication "
                "failure; §22.1's outcomes do not include an exception, and §7.3.8 "
                "L1677-1679 keeps the outcome REJECTED"
            )
        assert outcome_of(result) is AdmissionOutcome.REJECTED, (
            f"got {outcome_of(result)}"
        )
        assert reason_of(result) == SIGNATURE_INVALID, reason_of(result)


# --------------------------------------------------------------------------
# obligations 18 and 19 — the two boundaries
# --------------------------------------------------------------------------


# The call-site scanner this obligation used to carry lived here. It matched a
# callee by NAME ONLY, which can neither name a call site INDIVIDUALLY nor see an
# aliased call — and §7.3.13 requires both. It now lives in
# `tests/evidence/callsite_identity.py`, which resolves aliases within their own
# scope, records a per-call identity, and reports the forms it cannot resolve
# instead of dropping them.


#: §7.3.13 — the APPROVED call-site set for the tree under test.
#:
#: EMPTY HERE, AND THAT IS THE ASSERTION RATHER THAN AN OMISSION. §7.3.13
#: separates the BASELINE check (the approved set is empty and so is the observed
#: set) from the CANDIDATE check (the observed set equals what the connecting
#: change declares). This tree is the BASELINE. PR-2 — the joint change — fills
#: this mapping with the identities it creates, in the same change that creates
#: them, and that diff IS the approval artifact.
APPROVED_CALL_SITES: dict[tuple[str, str, str, str, str], object] = {}


def _scan_planted(tmp_path, source: str):
    """Write ONE planted module into `tmp_path` and scan THAT directory."""
    (tmp_path / "zz_planted.py").write_text(source, encoding="utf-8")
    return scan_tree(tmp_path, skip_paths=())


def _problems(observed, approved, unresolved, failures=()):
    """`findings`, with the scan's failure list available to pass through.

    `failures` defaults to empty so a fixture that cannot fail to parse need not
    thread it; a test that DOES scan a real tree passes it, because a file the
    scan could not read has unknown call sites and must not disappear.
    """
    return findings(observed, approved, unresolved, failures)


class TestObligation18ApprovedCallSiteSet:
    """§7.3.7's obligation as amended, defined by §7.3.13 (Amendment 9).

    The obligation was "the absence of a production non-test writer". It is now
    the EXACT APPROVED CALL-SITE SET: each production call site of `admit` or
    `admit_to_store` named INDIVIDUALLY, the baseline set being empty and the
    candidate set equalling what the connecting change declares.

    TWO THINGS THIS CLASS IS NOT. It is not a completeness claim — static scanning
    cannot establish the absence of arbitrary Python dynamic behaviour, and the
    blind-spot list the scanner carries is transparency rather than an acceptance
    criterion. And it is not a count check: every assertion below compares
    IDENTITIES, which is what lets 18c fail a substitution whose count is
    unchanged.
    """

    def test_obligation_18a_the_approved_call_site_set_is_exact(self):
        """The baseline/candidate assertion, over the real production tree.

        An empty approved set on a tree with no production call site is the
        baseline check; the same code serves the candidate check once PR-2 fills
        the mapping. The comparison is §7.3.13's — mapping equality in both
        directions, never a count.
        """
        observed, unresolved, failures = scan_tree(REPO_ROOT, skip_paths=("tests",))
        problems = _problems(observed, APPROVED_CALL_SITES, unresolved, failures)
        assert problems == [], (
            "the production call-site set does not equal the approved set "
            "(§7.3.13). Each finding below names ONE identity: "
            f"{problems}"
        )

    def test_obligation_18b_the_scan_can_find_a_call_site(self):
        """The positive control. A scan that cannot find a call site proves
        nothing about there being none — the same reason §12.1's gate exists."""
        observed, _, _ = scan_tree(REPO_ROOT / "tests")
        assert observed, (
            "the scan found no call of admit/admit_to_store anywhere under "
            "tests/, which is where the acceptance suite calls them; a scanner "
            "that finds nothing cannot be evidence that production has nothing"
        )

    def test_obligation_18c_a_substitution_with_an_unchanged_count_fails(self, tmp_path):
        """DELETE ONE APPROVED CALL, ADD ANOTHER IN THE SAME SCOPE, COUNT UNCHANGED.

        This is the case a count-only approval passes and §7.3.13 must fail. The
        two trees hold the SAME NUMBER of calls in the SAME scope; what differs is
        which call it is.
        """
        before = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        after = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    marker = None\n"
            "    return admit(record, producer_proof=proof) if marker is None else marker\n"
        )

        observed_before, _, _ = _scan_planted(tmp_path, before)
        approved = group_by_key(observed_before)
        assert len(approved) == 1, "the fixture must plant exactly one call site"

        (tmp_path / "zz_planted.py").write_text(after, encoding="utf-8")
        observed_after, unresolved_after, failures_after = scan_tree(tmp_path, skip_paths=())

        assert len(observed_after) == len(observed_before), (
            "the fixture must keep the COUNT unchanged — that is the whole point "
            "of the case"
        )
        problems = _problems(observed_after, approved, unresolved_after)
        assert any("APPROVED call site NOT FOUND" in problem for problem in problems), (
            "the approved identity is gone and must be reported as missing: "
            f"{problems}"
        )
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            "the substituted call site is not the approved one and must be "
            f"reported: {problems}"
        )

    def test_obligation_18d_two_calls_in_one_scope_are_two_identities(self, tmp_path):
        """A second call in one scope is a SECOND identity, not a bigger count."""
        source = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    admit(record, producer_proof=proof)\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        observed, unresolved, failures = _scan_planted(tmp_path, source)
        assert len(observed) == 2, f"expected two identities, saw {observed}"

        first = sorted(observed, key=lambda item: item.ast_path)[0]
        approved = group_by_key([first])
        problems = _problems(observed, approved, unresolved)
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            "approving one of two calls in a scope must leave the other "
            f"unapproved: {problems}"
        )

    def test_obligation_18e_aliases_resolve_to_the_canonical_entrypoint(self, tmp_path):
        """A resolved alias is counted under its CANONICAL name (§7.3.13)."""
        source = (
            "import plugins.evidence.admission as adm\n"
            "from plugins.evidence import admit_to_store as persist\n"
            "\n"
            "\n"
            "def submit(record, store, proof):\n"
            "    persist(record, store=store, producer_proof=proof)\n"
            "    return adm.admit(record, producer_proof=proof)\n"
        )
        observed, unresolved, failures = _scan_planted(tmp_path, source)
        assert not unresolved, f"both forms are supported and must resolve: {unresolved}"
        assert sorted(item.entrypoint for item in observed) == ["admit", "admit_to_store"], (
            "an alias must be recorded under its canonical entry point, never "
            f"under the local binding name: {observed}"
        )

    def test_obligation_18f_an_unapproved_addition_fails(self, tmp_path):
        """A call site added outside the approved set is a finding."""
        base = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        observed, _, _ = _scan_planted(tmp_path, base)
        approved = group_by_key(observed)

        grown = base + (
            "\n"
            "\n"
            "def also_submit(record, proof):\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        (tmp_path / "zz_planted.py").write_text(grown, encoding="utf-8")
        observed_grown, unresolved_grown, failures_grown = scan_tree(tmp_path, skip_paths=())
        problems = _problems(observed_grown, approved, unresolved_grown)
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            f"an added call site must be reported: {problems}"
        )

    @pytest.mark.parametrize(
        "planted",
        [
            pytest.param(
                "import plugins.evidence as evidence\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    return getattr(evidence, "admit")(record, producer_proof=proof)\n',
                id="getattr-acquisition",
            ),
            pytest.param(
                "from functools import partial\n"
                "from plugins.evidence import admit\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    return partial(admit, record, producer_proof=proof)()\n",
                id="partial-application",
            ),
            pytest.param(
                "CALLABLES = {}\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    return CALLABLES["admit_to_store"](record, producer_proof=proof)\n',
                id="container-dispatch",
            ),
        ],
    )
    def test_obligation_18g_unresolvable_forms_fail_closed(self, planted: str, tmp_path):
        """§7.3.13 — a form the scanner cannot resolve MUST FAIL, never be
        silently treated as 'no call site here'.

        Each case below is a call that NAMES an entry point and cannot be resolved
        to one. A check that reported nothing here would be reporting silence as
        safety.
        """
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        problems = _problems(observed, {}, unresolved)
        assert problems, (
            "an unresolvable form produced no finding, which is exactly the "
            f"silence §7.3.13 refuses:\n{planted}"
        )
        assert any("UNRESOLVED production call form" in problem for problem in problems), (
            f"the form must be reported as UNRESOLVED rather than dropped: {problems}"
        )

    def test_obligation_18h_producer_proof_must_be_an_explicit_keyword(self, tmp_path):
        """§7.3.13's `proof_kwarg` — an explicit keyword, never a `**mapping`.

        A splat cannot be verified from the source, so the clause refuses it
        rather than assuming the key is inside the expansion.
        """
        explicit = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        observed, unresolved, failures = _scan_planted(tmp_path, explicit)
        assert observed[0].proof_kwarg is True
        assert not [
            problem for problem in _problems(observed, {}, unresolved) if "producer_proof" in problem
        ], "an explicit producer_proof keyword must not be reported as missing"

        splatted = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, envelope):\n"
            "    return admit(record, **envelope)\n"
        )
        (tmp_path / "zz_planted.py").write_text(splatted, encoding="utf-8")
        observed_splat, unresolved_splat, failures_splat = scan_tree(tmp_path, skip_paths=())
        assert observed_splat[0].proof_kwarg is False
        problems = _problems(observed_splat, {}, unresolved_splat)
        assert any("MISSING producer_proof KEYWORD" in problem for problem in problems), (
            f"a `**mapping` expansion does not satisfy the clause: {problems}"
        )

    @pytest.mark.parametrize(
        "planted",
        [
            pytest.param(
                "import plugins.evidence as evidence\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    writer = getattr(evidence, "admit")\n'
                "    return writer(record, producer_proof=proof)\n",
                id="a-getattr-acquired-then-called",
            ),
            pytest.param(
                "from functools import partial\n"
                "from plugins.evidence import admit\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    writer = partial(admit, record, producer_proof=proof)\n"
                "    return writer()\n",
                id="b-partial-created-then-called",
            ),
            pytest.param(
                "import importlib\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    mod = importlib.import_module("plugins.evidence.admission")\n'
                "    return mod.admit(record, producer_proof=proof)\n",
                id="c-dynamic-import-result-called",
            ),
            pytest.param(
                "REGISTRY = {}\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    writer = REGISTRY["admit"]\n'
                "    return writer(record, producer_proof=proof)\n",
                id="d-container-callable-called",
            ),
            pytest.param(
                "from plugins.evidence import admit, admit_to_store\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    writer = admit\n"
                "    writer = admit_to_store\n"
                "    return writer(record, producer_proof=proof)\n",
                id="e-ambiguous-local-name",
            ),
        ],
    )
    def test_obligation_18i_acquired_then_called_forms_fail_closed(self, planted: str, tmp_path):
        """THE ACQUISITION IS UNSUPPORTED EVEN WHEN THE CALL LOOKS ORDINARY.

        Every case below obtains a callable by a form §7.3.13 does not support and
        then calls it through a NAME. Checking only the immediately-invoked shape —
        `getattr(...)(...)`, `partial(...)()`, `container[...](...)` — would see an
        ordinary call to an unknown local and report NOTHING, which is precisely
        the silence the clause refuses.

        The rule that catches them is that the unsupported acquisition is carried
        FORWARD onto the name it binds, so the later call is reported.
        """
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        problems = _problems(observed, {}, unresolved, failures)
        assert problems, (
            "an acquired-then-called form produced no finding, which is exactly "
            f"the silence §7.3.13 refuses:\n{planted}"
        )
        assert any("UNRESOLVED production call form" in problem for problem in problems), (
            f"the form must be reported as UNRESOLVED rather than dropped: {problems}"
        )

    def test_obligation_18j_a_changed_callee_form_is_not_the_approved_site(self, tmp_path):
        """THE CALLEE'S ORIGINAL FORM IS PART OF THE IDENTITY.

        Two calls at the SAME scope, the SAME AST path, with the SAME arguments,
        reaching the SAME canonical entry point — differing ONLY in how the callee
        is spelled. An identity that recorded the canonical entry point alone
        would call these one call site, and an approval of the first would silently
        authorise the second.
        """
        direct = (
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    return admit(record, producer_proof=proof)\n"
        )
        # SAME line count and SAME shape: only the callee spelling differs, so the
        # ast_path is identical and the callee is the only variable.
        aliased = (
            "from plugins.evidence import admit as submit_alias\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    return submit_alias(record, producer_proof=proof)\n"
        )

        observed_direct, unresolved_direct, failures_direct = _scan_planted(tmp_path, direct)
        approved = group_by_key(observed_direct)
        assert len(approved) == 1, "the fixture must plant exactly one call site"

        (tmp_path / "zz_planted.py").write_text(aliased, encoding="utf-8")
        observed_alias, unresolved_alias, failures_alias = scan_tree(tmp_path, skip_paths=())

        assert len(observed_direct[0].fingerprint) == 64, (
            "the fingerprint is the FULL SHA-256 hex digest — 64 characters, not "
            "truncated. A shortened digest is a DIFFERENT identity with a weaker "
            "collision assumption than AI-05 §7.3.13 states"
        )
        assert all(character in "0123456789abcdef" for character in observed_direct[0].fingerprint), (
            "the fingerprint must be lowercase hexadecimal"
        )
        assert observed_direct[0].callee, "the original callee form must be recorded"
        assert observed_alias[0].callee != observed_direct[0].callee, (
            "the two forms differ in the callee, so their `callee` fields must differ"
        )

        assert len(observed_alias) == 1, "the fixture must keep the count unchanged"
        assert observed_alias[0].entrypoint == observed_direct[0].entrypoint, (
            "both forms must resolve to the SAME canonical entry point — otherwise "
            "this test is not isolating the callee form"
        )
        assert observed_alias[0].ast_path == observed_direct[0].ast_path, (
            "both forms must sit at the SAME AST path — otherwise this test is not "
            "isolating the callee form"
        )
        assert observed_alias[0].key != observed_direct[0].key, (
            "the two forms are two DIFFERENT call sites and must not share an "
            "identity; recording only the canonical entry point would collapse them"
        )
        problems = _problems(observed_alias, approved, unresolved_alias, failures_alias)
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            f"the new form must be reported as unapproved: {problems}"
        )
        assert any("APPROVED call site NOT FOUND" in problem for problem in problems), (
            f"the old approval must be reported as gone: {problems}"
        )

    def test_obligation_18k_an_unreadable_module_fails_the_scan(self, tmp_path):
        """A FILE THE SCAN CANNOT READ HAS UNKNOWN CALL SITES, AND UNKNOWN IS NOT NONE.

        A scanner that skipped it would report the call sites it happened to see
        and call the result clean. §7.3.13 makes an unreadable module an auditable
        failure instead.
        """
        (tmp_path / "zz_broken.py").write_text("def oops(:\n    pass\n", encoding="utf-8")
        observed, unresolved, failures = scan_tree(tmp_path, skip_paths=())
        assert observed == [], "the fixture must plant no parseable call site"
        assert failures, (
            "the unparseable module must be reported as a scan failure, not "
            "skipped silently"
        )
        assert failures[0].path.endswith("zz_broken.py")
        problems = _problems(observed, {}, unresolved, failures)
        assert any("UNREADABLE production module" in problem for problem in problems), (
            f"a scan failure must drive the check to FAIL: {problems}"
        )

    @pytest.mark.parametrize(
        "planted",
        [
            pytest.param(
                "import plugins.evidence as ev\n"
                "\n"
                "\n"
                "def submit(record, field, proof):\n"
                "    writer = getattr(ev, field)\n"
                "    return writer(record, producer_proof=proof)\n",
                id="dynamic-attribute-name-parameter",
            ),
            pytest.param(
                "import plugins.evidence as ev\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                '    field = "admit"\n'
                "    writer = getattr(ev, field)\n"
                "    return writer(record, producer_proof=proof)\n",
                id="attribute-name-through-a-variable",
            ),
            pytest.param(
                "import plugins.evidence as admissions\n"
                "\n"
                "\n"
                "def submit(record, field, proof):\n"
                "    writer = getattr(admissions, field)\n"
                "    return writer(record, producer_proof=proof)\n",
                id="evidence-package-under-an-import-alias",
            ),
            pytest.param(
                "from functools import partial as p\n"
                "from plugins.evidence import admit\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    writer = p(admit, record, producer_proof=proof)\n"
                "    return writer()\n",
                id="aliased-partial-acquisition",
            ),
            pytest.param(
                "import functools as ft\n"
                "from plugins.evidence import admit\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    writer = ft.partial(admit, record, producer_proof=proof)\n"
                "    return writer()\n",
                id="module-qualified-partial-acquisition",
            ),
            pytest.param(
                "from functools import partial as p\n"
                "from plugins.evidence import admit\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    return p(admit, record)(producer_proof=proof)\n",
                id="aliased-immediately-invoked-acquisition",
            ),
        ],
    )
    def test_obligation_18l_dynamic_names_and_aliased_acquirers_fail_closed(
        self, planted: str, tmp_path
    ):
        """THE RECEIVER DECIDES, NOT THE SPELLING OF THE ATTRIBUTE — AND AN ALIASED
        ACQUISITION IS THE SAME HOLE UNDER ANOTHER NAME.

        `getattr(ev, field)` may be `admit` at run time. "We could not read the
        name" is NOT "it is not an entry point", and an implementation that assumed
        otherwise would report a clean scan for a call it never resolved. The same
        applies to `partial` reached through an alias or through its module, which
        is why the acquirer is resolved through the scope's own bindings rather
        than by matching three literal spellings.
        """
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        problems = _problems(observed, {}, unresolved, failures)
        assert problems, (
            "the form produced NO finding, which is the silence §7.3.13 refuses:"
            f"\n{planted}"
        )
        assert any("UNRESOLVED production call form" in problem for problem in problems), (
            f"the form must be reported as UNRESOLVED rather than dropped: {problems}"
        )
        assert observed == [], (
            "nothing here is a RESOLVED call site, so the identity list must be "
            f"empty — got {observed}"
        )

    def test_obligation_18m_a_resolvable_non_entry_point_attribute_is_not_reported(self, tmp_path):
        """THE CONTROL THAT KEEPS 18l FROM MEANING "BLOCK EVERY getattr".

        `getattr(ev, "ExecutionPayload")` names a real attribute of the package
        that is NOT an admission entry point, and a scanner that reported it would
        be blocking the form rather than resolving it. The rule is about what
        cannot be RESOLVED — not about the word `getattr`.
        """
        planted = (
            "import plugins.evidence as ev\n"
            "\n"
            "\n"
            "def fetch():\n"
            '    return getattr(ev, "ExecutionPayload")\n'
        )
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        problems = _problems(observed, {}, unresolved, failures)
        assert problems == [], (
            "a resolvable attribute that is not an entry point must NOT be "
            f"reported — otherwise the rule has become a blanket block: {problems}"
        )

    # -- the intra-package exception, bounded by uniqueness --------------------

    @staticmethod
    def _plant_admission(tmp_path, body: str):
        """Plant a `plugins/evidence/admission.py` and scan its root.

        The exception is keyed on THAT path, so a fixture anywhere else would not
        exercise it.
        """
        target = tmp_path / "plugins" / "evidence" / "admission.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return scan_tree(tmp_path, skip_paths=())

    _ADMIT_DEF = (
        "def admit(raw, *, producer_proof=None, clock=None):\n"
        "    return raw\n"
        "\n"
        "\n"
    )

    def test_obligation_18n_the_intra_package_edge_is_a_verified_observed_identity(self):
        """THE EXCEPTION GRANTS A VERIFIED IDENTITY, NOT A MATCHING TRIPLE.

        This is asserted against the REAL `plugins/evidence/admission.py`, because
        a synthetic fixture at the same path is a DIFFERENT call site: its AST path
        and fingerprint differ, and it must not be excused by sharing a triple.

        An earlier revision of this test planted a fixture and asserted only
        `findings() == []`. MEASURED, that fixture's call was classified
        UNRESOLVED — observed=0, unresolved=1 — so the clean result came from a lone
        unresolved candidate being excused, not from the intended call site being
        recognised. The assertion below therefore names the identity it expects.
        """
        observed, unresolved, failures = scan_tree(REPO_ROOT, skip_paths=("tests",))
        approved_identity = callsite_identity.INTRA_PACKAGE_CALL_SITE

        matches = [identity for identity in observed if identity.key == approved_identity]
        assert len(matches) == 1, (
            "the declared internal call site must be found EXACTLY ONCE as an "
            "OBSERVED identity. If `plugins/evidence/admission.py` changed, this "
            "fails and the identity must be re-approved rather than re-derived: "
            f"observed={[(i.path, i.lineno, i.callee) for i in observed]}"
        )
        assert matches[0].scope == "admit_to_store", (
            f"the exception must name the definition site's own caller: {matches[0]}"
        )

        problems = _problems(observed, {}, unresolved, failures)
        assert problems == [], (
            "with the verified internal call site excused, nothing else may be "
            f"reported on the real production tree: {problems}"
        )

    def test_obligation_18t_a_lone_unresolved_candidate_is_not_excused(self, tmp_path):
        """ONE CANDIDATE IS NOT ENOUGH WHEN THAT CANDIDATE IS UNRESOLVED.

        The scope holds exactly ONE entry matching the exception's triple, and it
        is an immediately-invoked acquisition. A rule that excused a lone
        candidate would grant the exception on the strength of "we could not
        resolve this call" — the opposite of what an approval is.
        """
        observed, unresolved, failures = self._plant_admission(
            tmp_path,
            "from functools import partial\n"
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def admit_to_store(raw, *, store=None, producer_proof=None, clock=None):\n"
            "    return partial(admit, raw)(producer_proof=producer_proof)\n",
        )
        candidates = [
            call
            for call in unresolved
            if (call.path, call.scope, call.entrypoint) == callsite_identity.INTRA_PACKAGE_EDGE
        ]
        assert len(candidates) == 1, (
            "the fixture must leave EXACTLY ONE candidate, so the test measures the "
            f"lone-candidate case rather than ambiguity: unresolved={unresolved}"
        )
        problems = _problems(observed, {}, unresolved, failures)
        assert any("INTRA-PACKAGE EXCEPTION NOT APPLIED" in problem for problem in problems), (
            f"a lone UNRESOLVED candidate must not be excused: {problems}"
        )
        assert any("UNRESOLVED production call form" in problem for problem in problems), (
            f"and it must be reported on its own terms: {problems}"
        )

    def test_obligation_18u_a_lone_aliased_candidate_is_not_excused(self, tmp_path):
        """A LONE OBSERVED CANDIDATE IS NOT EXCUSED EITHER, IF ITS IDENTITY DIFFERS.

        The alias resolves to the same canonical entry point and sits in the same
        scope, so the TRIPLE matches. The callee, the AST path and the fingerprint
        do not, so the call site is not the approved one.
        """
        observed, unresolved, failures = self._plant_admission(
            tmp_path,
            "from plugins.evidence import admit as persist\n"
            "\n"
            "\n"
            "def admit_to_store(raw, *, store=None, producer_proof=None, clock=None):\n"
            "    return persist(raw, producer_proof=producer_proof)\n",
        )
        candidates = [
            identity
            for identity in observed
            if (identity.path, identity.scope, identity.entrypoint)
            == callsite_identity.INTRA_PACKAGE_EDGE
        ]
        assert len(candidates) == 1, (
            "the fixture must leave EXACTLY ONE observed candidate, so the test "
            f"measures identity rather than ambiguity: observed={observed}"
        )
        assert candidates[0].entrypoint == "admit", "the alias must still resolve"
        assert candidates[0].key != callsite_identity.INTRA_PACKAGE_CALL_SITE, (
            "the aliased call must NOT share the approved identity"
        )
        problems = _problems(observed, {}, unresolved, failures)
        assert any("INTRA-PACKAGE EXCEPTION NOT APPLIED" in problem for problem in problems), (
            f"a differing identity must not be excused: {problems}"
        )
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            f"and the call site must be reported: {problems}"
        )

    def test_obligation_18o_a_second_call_in_the_same_scope_is_not_excused(self, tmp_path):
        """THE EXCEPTION NAMES ONE CALL SITE, NOT A SCOPE.

        A second `admit(...)` in the SAME `admit_to_store` shares all three fields
        of the exception's key. An exclusion over that triple alone would swallow
        it silently; the exception is bounded by uniqueness instead, so an
        ambiguous match excuses NOTHING and both calls are reported with it.
        """
        observed, unresolved, failures = self._plant_admission(
            tmp_path,
            self._ADMIT_DEF
            + "def admit_to_store(raw, *, store=None, producer_proof=None, clock=None):\n"
            + "    first = admit(raw, producer_proof=producer_proof)\n"
            + "    return admit(first, producer_proof=producer_proof)\n",
        )
        problems = _problems(observed, {}, unresolved, failures)
        assert any("INTRA-PACKAGE EXCEPTION IS AMBIGUOUS" in problem for problem in problems), (
            f"two matches for a one-call-site exception must be reported: {problems}"
        )
        reported = [
            problem
            for problem in problems
            if "UNRESOLVED production call form" in problem or "UNAPPROVED call site" in problem
        ]
        assert len(reported) == 2, (
            "NEITHER call may be excused once the match is ambiguous — both must "
            f"appear, not just one: {problems}"
        )

    def test_obligation_18p_a_same_key_unresolved_form_is_not_excused(self, tmp_path):
        """A DIFFERENT FORM SHARING THE KEY IS NOT THE EXCUSED CALL SITE.

        The second call below is an immediately-invoked acquisition, not the
        plain internal call the exception is for — yet it shares path, scope and
        entry point with it. Sharing the key must not be enough.
        """
        observed, unresolved, failures = self._plant_admission(
            tmp_path,
            self._ADMIT_DEF
            + "from functools import partial\n"
            + "\n"
            + "\n"
            + "def admit_to_store(raw, *, store=None, producer_proof=None, clock=None):\n"
            + "    result = admit(raw, producer_proof=producer_proof)\n"
            + "    other = partial(admit, raw)(producer_proof=producer_proof)\n"
            + "    return result or other\n",
        )
        problems = _problems(observed, {}, unresolved, failures)
        assert any("INTRA-PACKAGE EXCEPTION IS AMBIGUOUS" in problem for problem in problems), (
            f"a second same-key entry must make the match ambiguous: {problems}"
        )
        assert any("immediately-invoked acquisition" in problem for problem in problems), (
            f"the acquisition form must be reported on its own terms: {problems}"
        )
        assert problems, "sharing the exception's key must not produce a clean result"

    def test_obligation_18s_one_observed_plus_one_unresolved_is_two_candidates(self, tmp_path):
        """THE EXCEPTION MAKES **ONE** DECISION ACROSS BOTH LISTS.

        A call site is not "one observed plus one unresolved". Judging the lists
        separately let a single observed entry and a single unresolved entry each
        satisfy its own `len(...) == 1` and BOTH be excused — two excused entries
        from an exception that names one call site.

        The fixture puts ONE entry of each kind in the SAME `admit_to_store` scope,
        sharing all three fields of the exception's key.
        """
        planted = (
            "from functools import partial\n"
            "from plugins.evidence import admit\n"
            "\n"
            "\n"
            "def admit_to_store(raw, *, store=None, producer_proof=None, clock=None):\n"
            "    first = admit(raw, producer_proof=producer_proof)\n"
            "    other = partial(admit, raw)(producer_proof=producer_proof)\n"
            "    return first or other\n"
        )
        observed, unresolved, failures = self._plant_admission(tmp_path, planted)

        observed_candidates = [
            identity
            for identity in observed
            if (identity.path, identity.scope, identity.entrypoint)
            == callsite_identity.INTRA_PACKAGE_EDGE
        ]
        unresolved_candidates = [
            call
            for call in unresolved
            if (call.path, call.scope, call.entrypoint) == callsite_identity.INTRA_PACKAGE_EDGE
        ]

        # THE FIXTURE MUST COVER THE CROSS-CATEGORY COMBINATION. If either side is
        # empty this test is not exercising what it claims to, and it says so
        # rather than passing vacuously.
        assert len(observed_candidates) == 1, (
            "the fixture must place exactly ONE observed candidate in the scope; "
            f"observed={observed} unresolved={unresolved}"
        )
        assert len(unresolved_candidates) == 1, (
            "the fixture must place exactly ONE unresolved candidate in the scope; "
            f"observed={observed} unresolved={unresolved}"
        )
        assert (
            observed_candidates[0].path,
            observed_candidates[0].scope,
            observed_candidates[0].entrypoint,
        ) == (
            unresolved_candidates[0].path,
            unresolved_candidates[0].scope,
            unresolved_candidates[0].entrypoint,
        ), "both candidates must share the exception's triple, or this proves nothing"

        problems = _problems(observed, {}, unresolved, failures)
        assert any("INTRA-PACKAGE EXCEPTION IS AMBIGUOUS" in problem for problem in problems), (
            f"two pooled candidates must be reported as ambiguous: {problems}"
        )
        assert any("2 entries match" in problem for problem in problems), (
            "the ambiguity must state the POOLED total, not a per-list count: "
            f"{problems}"
        )
        assert any(
            "UNRESOLVED production call form" in problem and "immediately-invoked" in problem
            for problem in problems
        ), f"the unresolved candidate must be reported on its own terms: {problems}"
        assert any("UNAPPROVED call site" in problem for problem in problems), (
            "NEITHER candidate may be excused once the pooled total is two — the "
            f"observed one must be reported too: {problems}"
        )

    # -- dotted imports and resolved entry aliases -----------------------------

    @pytest.mark.parametrize(
        "planted",
        [
            pytest.param(
                "import plugins.evidence\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    return plugins.evidence.admit(record, producer_proof=proof)\n",
                id="unaliased-dotted-package",
            ),
            pytest.param(
                "import plugins.evidence.admission\n"
                "\n"
                "\n"
                "def submit(record, proof):\n"
                "    return plugins.evidence.admission.admit(record, producer_proof=proof)\n",
                id="unaliased-dotted-submodule",
            ),
        ],
    )
    def test_obligation_18q_an_unaliased_dotted_import_resolves_to_the_entry_point(
        self, planted: str, tmp_path
    ):
        """AN UNALIASED DOTTED IMPORT BINDS ITS ROOT, AND THE PATH MUST NOT DOUBLE.

        `import plugins.evidence` binds the name `plugins`, not the name
        `plugins.evidence`. Binding the full path made the next expansion produce
        `plugins.evidence.evidence.admit` — a path that does not exist, which was
        still classified as evidence and so hid the defect rather than failing on
        it. The assertion below checks the EXPANSION ITSELF, because the
        downstream effect alone cannot see the difference.
        """
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        assert observed, (
            "the call must resolve to a canonical entry point and appear in the "
            f"observed set; a silent empty result is the failure this guards: "
            f"observed={observed} unresolved={unresolved}"
        )
        assert observed[0].entrypoint == "admit"
        assert not unresolved, f"no form here is unresolvable: {unresolved}"

        tree = ast.parse(planted)
        scopes = callsite_identity._Scopes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "evidence":
                expanded = scopes.dotted(node, scopes.for_node(node))
                assert expanded == "plugins.evidence", (
                    f"the dotted expansion doubled: got {expanded!r}"
                )

    def test_obligation_18r_a_resolved_entry_alias_is_a_partial_target(self, tmp_path):
        """AN ALIAS IS AN ENTRY POINT IN ITS OWN SCOPE, INCLUDING AS A partial TARGET.

        `persist` is `admit`. `partial(persist, ...)` is an acquisition of an entry
        point, and the rule must find that through the scope's bindings rather than
        through a special case for the name `persist`.
        """
        planted = (
            "from functools import partial\n"
            "from plugins.evidence import admit as persist\n"
            "\n"
            "\n"
            "def submit(record, proof):\n"
            "    writer = partial(persist, record, producer_proof=proof)\n"
            "    return writer()\n"
        )
        observed, unresolved, failures = _scan_planted(tmp_path, planted)
        problems = _problems(observed, {}, unresolved, failures)
        assert observed == [], (
            "the call must NOT be recorded as a resolved direct call site — it is "
            f"an acquisition and a later call through a name: {observed}"
        )
        assert problems, (
            "the acquisition must be carried onto `writer` and the later call must "
            f"be reported: observed={observed} unresolved={unresolved}"
        )
        assert any("UNRESOLVED production call form" in problem for problem in problems), (
            f"the later call must be UNRESOLVED: {problems}"
        )


def load_layer0_policy():
    """`scripts/ci/layer0_policy.py` imported by path, not by package.

    It is a script, and its only entry point is guarded by
    `if __name__ == "__main__"`, so importing it executes no check. `ROOT` is
    derived from the file's own location, so the imported module checks the real
    repository.
    """
    path = REPO_ROOT / "scripts" / "ci" / "layer0_policy.py"
    spec = importlib.util.spec_from_file_location("ai05_layer0_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestObligation19NoCallerSelectedTrustRoot:
    """§7.3.7 L1660, by the checker's RETURN VALUE.

    The predicate is called directly and its result asserted. Running the Layer 0
    gate as a subprocess and reading its exit code would establish only that the
    script ran; the obligation is about what the check FOUND, so the check's own
    return value is the evidence.
    """

    def test_obligation_19_no_violation_is_reported(self):
        module = load_layer0_policy()
        problems = module.check_evidence_producer_authentication()
        assert problems == [], (
            "§31.3's NO CALLER-SELECTED TRUST ROOT and IMMUTABLE STATE rules are "
            "reported violated by the checker itself: " + repr(problems)
        )

    def test_obligation_19_the_rule_can_identify_its_target_violation(
        self, tmp_path, monkeypatch
    ):
        """The positive control, run against a SYNTHETIC tree.

        A non-empty constant does not show the rule can fire, so this control
        gives the checker a tree in which the target violation is planted and
        requires it to be REPORTED — and, first, requires the same tree WITHOUT
        the violation to be reported clean. Only the checker's `ROOT` is
        redirected, and only inside this test: the checker's logic, its scans and
        the real repository are untouched, and 19a runs against the real tree.

        The variable name in the synthetic reader is a plainly-synthetic one,
        never the designated name, so this control cannot be mistaken for a
        second reader of the real configuration.
        """
        module = load_layer0_policy()
        attribute = getattr(module, "EVIDENCE_TRUST_ENV_ATTRIBUTE", "ENV_NAME")
        synthetic_variable = "AT1B_SYNTHETIC_TRUST_CONFIGURATION"

        tree = tmp_path / "repo"
        package = tree / "plugins" / "evidence"
        harness_dir = tree / "tests" / "evidence"
        package.mkdir(parents=True)
        harness_dir.mkdir(parents=True)
        (package / "__init__.py").write_text(
            "from plugins.evidence.producer_auth import authenticate\n",
            encoding="utf-8",
        )
        (harness_dir / "trust_harness.py").write_text(
            f'{attribute} = "{synthetic_variable}"\n', encoding="utf-8"
        )

        def write_reader(*, violating):
            parameters = "raw, proof, trust=None" if violating else "raw, proof"
            (package / "producer_auth.py").write_text(
                f'{attribute} = "{synthetic_variable}"\n'
                "\n"
                "\n"
                f"def authenticate({parameters}):\n"
                "    return None\n",
                encoding="utf-8",
            )

        monkeypatch.setattr(module, "ROOT", tree)
        write_reader(violating=False)
        clean = module.check_evidence_producer_authentication()
        assert not any("authenticate" in problem for problem in clean), (
            "the synthetic tree without the planted parameter was reported "
            f"against, so this control proves nothing: {clean}"
        )

        write_reader(violating=True)
        problems = module.check_evidence_producer_authentication()
        assert any(
            "authenticate" in problem and "trust" in problem for problem in problems
        ), (
            "the checker must report a PUBLIC function that accepts a trust root "
            "— a rule that cannot identify its target violation cannot establish "
            f"its absence. Reported instead: {problems}"
        )


# --------------------------------------------------------------------------
# obligation 20 — no coupling from an authentication failure to Guard
# --------------------------------------------------------------------------


class TestObligation20NoGuardCoupling:
    """§7.3.7 L1661 and §7.3.8 L1759-1762."""

    def test_obligation_20_authentication_failure_is_not_a_guard_deny(self):
        requires("regression")
        raw = observation()
        good = proof_for_record(raw)
        result = admit(
            raw,
            producer_proof=dict(good, signature="0" * 128),
            clock=lambda: FIXED_CLOCK,
        )
        assert outcome_of(result) is AdmissionOutcome.REJECTED, outcome_of(result)
        assert reason_of(result) == SIGNATURE_INVALID, reason_of(result)
        assert reason_of(result) not in {"DENY", "GUARD_DENY", "DENIED"}, (
            "an authentication failure is not a Guard deny, is not reported as "
            f"one and is not translated into one; got {reason_of(result)}"
        )
        assert not hasattr(result, "guard_decision") or getattr(
            result, "guard_decision", None
        ) is None, "no Guard result may be attached to an authentication failure"


# --------------------------------------------------------------------------
# obligation 21 — the reason-code precedence of §7.3.8
# --------------------------------------------------------------------------


class TestObligation21ReasonPrecedence:
    """§7.3.7 L1662-1663 and §7.3.8 L1740-1746: when step 7's published rule and
    authentication BOTH fail, step 7's reason is the one reported."""

    def test_obligation_21_step7_reason_wins(self):
        """The published rule must ACTUALLY fire, or the precedence is untested.

        §7.3.8 L1740-1746 states the precedence for a submission that "trips a
        published rule AND carries a bad proof". A published rule is one of
        §14.10's six credential rules, and `check_admission_rules` applies them to
        §14.10's own scanned paths — `payload.observed` among them. An unknown
        member does NOT trip one (shape is not step 7's question, §7.3.8
        L1747-1754), so the case below puts a credential-shaped value where the
        rule set looks, and pairs it with a well-formed envelope carrying a bad
        signature.
        """
        requires("regression")
        from plugins.evidence.errors import AdmissionRuleViolation

        base = observation()
        raw = mutate(
            base,
            payload=mutate(base["payload"], observed="token: not-a-real-credential"),
        )
        bad_proof = dict(proof_for_record(base), signature="0" * 128)
        result = admit(raw, producer_proof=bad_proof, clock=lambda: FIXED_CLOCK)
        assert outcome_of(result) is AdmissionOutcome.REJECTED, outcome_of(result)
        assert not str(reason_of(result)).startswith("AUTHENTICATION_"), (
            "step 7 runs before step 7b, so a submission that trips a published "
            "rule AND carries a bad proof is rejected with the RULE's reason and "
            "authentication is never reached; an authentication code here means "
            f"step 7b ran first, or the rule did not fire. Got {reason_of(result)}"
        )
        assert reason_of(result) == AdmissionRuleViolation.reason_code, (
            "the reason reported is the published rule's — the code §14.10 and "
            "§30 define for it, read from the error class rather than restated "
            f"here. Got {reason_of(result)}"
        )


# --------------------------------------------------------------------------
# obligation 22 — AI-05-CJ-1's vectors, byte for byte (§7.3.7 L1664-1665)
# --------------------------------------------------------------------------

#: §7.3.6 L1311-1317 — the fixed prefix, printed as hex by the contract.
VECTOR_PREFIX_HEX = (
    "776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66"
    "0031"
    "00"
)

#: §7.3.6 VECTOR 1, L1324-1327 — the mapping AS SUPPLIED, deliberately unsorted.
VECTOR_1_MAPPING_TEXT = (
    '{"schema_version":1,"kind":"OBSERVATION",'
    '"provenance":{"producer":"ai-03","producer_type":"service",'
    '"workspace_id":"ws-1"},'
    '"payload":{"family":"SOURCE_READ"}}'
)

#: §7.3.6 VECTOR 1, L1332 — the canonical text, ON ONE PHYSICAL LINE, and the
#: contract states it is 158 characters.
VECTOR_1_CANONICAL = (
    '{"kind":"OBSERVATION","payload":{"family":"SOURCE_READ"},'
    '"provenance":{"producer":"ai-03","producer_type":"service",'
    '"workspace_id":"ws-1"},"schema_version":1}'
)

#: §7.3.6 VECTOR 1, L1342 — printed "for cross-checking only".
VECTOR_1_CANONICAL_SHA256 = (
    "f4a1d5fcd69667991fde630a1df304c0d704926986e307a2203de6d3bb33e1ec"
)

#: §7.3.6 VECTOR 1, L1344-1351 — the signed input, 194 bytes, unwrapped.
VECTOR_1_SIGNED_INPUT_HEX = (
    "776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66"
    "003100"
    "7b226b696e64223a224f42534552564154494f4e222c227061796c6f6164223a7b"
    "2266616d696c79223a22534f555243455f52454144227d2c2270726f76656e616e"
    "6365223a7b2270726f6475636572223a2261692d3033222c2270726f6475636572"
    "5f74797065223a2273657276696365222c22776f726b73706163655f6964223a22"
    "77732d31227d2c22736368656d615f76657273696f6e223a317d"
)

#: §7.3.6 VECTOR 1, L1353-1357 — message_b64u, 259 characters, unwrapped.
VECTOR_1_MESSAGE_B64U = (
    "d29ya2JlbmNoLmV2aWRlbmNlLnByb2R1Y2VyLXByb29mADEAeyJraW5kIjoiT0JTRVJW"
    "QVRJT04iLCJwYXlsb2FkIjp7ImZhbWlseSI6IlNPVVJDRV9SRUFEIn0sInByb3ZlbmFu"
    "Y2UiOnsicHJvZHVjZXIiOiJhaS0wMyIsInByb2R1Y2VyX3R5cGUiOiJzZXJ2aWNlIiwid2"
    "9ya3NwYWNlX2lkIjoid3MtMSJ9LCJzY2hlbWFfdmVyc2lvbiI6MX0"
)

#: §7.3.6 VECTOR 2, L1364-1365 — "café" is c,a,f,U+00E9, NFC, NOT normalized.
VECTOR_2_MAPPING_TEXT = (
    '{"payload":{"subject":"café"},"kind":"OBSERVATION","schema_version":1}'
)

#: §7.3.6 VECTOR 2, L1369.
VECTOR_2_CANONICAL = (
    '{"kind":"OBSERVATION","payload":{"subject":"café"},"schema_version":1}'
)

#: §7.3.6 VECTOR 2, L1372 — FIVE bytes, and the point of the vector.
VECTOR_2_CAFE_UTF8_HEX = "636166c3a9"

#: §7.3.6 VECTOR 2, L1375-1380 — the signed input, unwrapped.
VECTOR_2_SIGNED_INPUT_HEX = (
    "776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66"
    "003100"
    "7b226b696e64223a224f42534552564154494f4e222c227061796c6f6164223a7b"
    "227375626a656374223a22636166c3a9227d2c22736368656d615f76657273696f"
    "6e223a317d"
)

#: §7.3.6 VECTOR 2, L1382-1385 — message_b64u, unwrapped.
VECTOR_2_MESSAGE_B64U = (
    "d29ya2JlbmNoLmV2aWRlbmNlLnByb2R1Y2VyLXByb29mADEAeyJraW5kIjoiT0JTRVJW"
    "QVRJT04iLCJwYXlsb2FkIjp7InN1YmplY3QiOiJjYWbDqSJ9LCJzY2hlbWFfdmVyc2lv"
    "biI6MX0"
)


def vector_mapping(text):
    import json

    return json.loads(text)


class TestObligation22Cj1Vectors:
    """§7.3.7 L1664-1665: AI-05-CJ-1's vectors (§7.3.6) reproduced BYTE FOR BYTE,
    including the non-ASCII vector and both negative controls.

    Only values the contract PRINTS are golden here. The signatures are not: the
    contract states no signature value is printed and none is normative
    (L1455-1459), so the negative controls sign on the spot with the test key.
    """

    def test_obligation_22a_vector_1_bytes(self):
        from plugins.evidence.signed_input import canonical_serialization, signed_input

        mapping = vector_mapping(VECTOR_1_MAPPING_TEXT)
        canonical = canonical_serialization(mapping)
        assert canonical == VECTOR_1_CANONICAL.encode("utf-8"), (
            "VECTOR 1's canonical text is a single line the contract prints "
            "verbatim (L1329-1332); the profile's output must equal its bytes"
        )
        assert len(VECTOR_1_CANONICAL) == 158, (
            "the contract states VECTOR 1's canonical text is 158 characters; "
            f"this module transcribed {len(VECTOR_1_CANONICAL)}"
        )
        assert hashlib.sha256(canonical).hexdigest() == VECTOR_1_CANONICAL_SHA256, (
            "the contract prints the sha256 of the canonical bytes for "
            "cross-checking (L1341-1342); it must match"
        )
        assert signed_input(mapping).hex() == VECTOR_1_SIGNED_INPUT_HEX, (
            "VECTOR 1's signed input is printed as 194 bytes of hex "
            "(L1344-1351); the profile must reproduce them exactly"
        )
        assert len(bytes.fromhex(VECTOR_1_SIGNED_INPUT_HEX)) == 194, (
            "the contract states the signed input is 194 bytes"
        )
        assert signed_input(mapping).hex().startswith(VECTOR_PREFIX_HEX), (
            "every signed input begins with the domain tag, a 0x00, the proof "
            "version '1' and another 0x00 (L1311-1317)"
        )
        encoded = base64.urlsafe_b64encode(signed_input(mapping)).rstrip(b"=").decode()
        assert encoded == VECTOR_1_MESSAGE_B64U, (
            "VECTOR 1's message_b64u is printed as 259 characters (L1353-1357) "
            "and must be reproduced exactly"
        )
        assert len(VECTOR_1_MESSAGE_B64U) == 259

    def test_obligation_22b_vector_2_non_ascii(self):
        from plugins.evidence.signed_input import canonical_serialization, signed_input

        mapping = vector_mapping(VECTOR_2_MAPPING_TEXT)
        assert mapping["payload"]["subject"] == "café", (
            "the contract's vector uses U+00E9 (L1366); a test that normalizes "
            "or escapes it is testing something else"
        )
        assert canonical_serialization(mapping) == VECTOR_2_CANONICAL.encode("utf-8"), (
            "VECTOR 2's canonical text is printed at L1369"
        )
        assert "café".encode("utf-8").hex() == VECTOR_2_CAFE_UTF8_HEX, (
            "'café' is FIVE UTF-8 bytes, not eight (L1371-1372)"
        )
        assert signed_input(mapping).hex() == VECTOR_2_SIGNED_INPUT_HEX, (
            "VECTOR 2's signed input is printed with the raw c3a9 bytes "
            "(L1375-1380)"
        )
        encoded = base64.urlsafe_b64encode(signed_input(mapping)).rstrip(b"=").decode()
        assert encoded == VECTOR_2_MESSAGE_B64U, (
            "VECTOR 2's message_b64u is printed at L1382-1385, with the fragment "
            "'YWbDqS' carrying 'café'"
        )
        assert "YWbDqS" in VECTOR_2_MESSAGE_B64U

    def _altered_tag_message(self):
        from plugins.evidence.signed_input import signed_input

        message = bytearray(signed_input(vector_mapping(VECTOR_1_MAPPING_TEXT)))
        message[0] = 0x78  # 'x' — §7.3.6 L1434
        return bytes(message)

    def _version_2_message(self):
        from plugins.evidence.signed_input import signed_input

        message = bytearray(signed_input(vector_mapping(VECTOR_1_MAPPING_TEXT)))
        assert message[34] == 0x31, (
            "VECTOR 3 states byte offset 34 is 31 ('1') in VECTOR 1 (L1395-1398)"
        )
        message[34] = 0x32  # '2'
        return bytes(message)

    def test_obligation_22c_vector_3_case_a_signature_refuses_first(self):
        requires("regression")
        raw = vector_mapping(VECTOR_1_MAPPING_TEXT)
        sig_a = proof_for("ai-03", raw)["signature"]  # a valid signature over VECTOR 1
        result = admit(
            raw,
            producer_proof=proof_with(self._version_2_message(), sig_a),
            clock=lambda: FIXED_CLOCK,
        )
        assert reason_of(result) == SIGNATURE_INVALID, (
            "VECTOR 3 CASE A: the version-2 message carried with VECTOR 1's "
            "signature does not verify, V5 is never reached, and a verifier that "
            f"reported a mismatch here would have compared before verifying "
            f"(L1406-1410); got {reason_of(result)}"
        )

    def test_obligation_22d_vector_3_case_b_reconstruction_refuses(self):
        requires("regression")
        from trust_harness import _private

        raw = vector_mapping(VECTOR_1_MAPPING_TEXT)
        sig_b = _private("ai-03").sign(self._version_2_message()).hex()
        result = admit(
            raw,
            producer_proof=proof_with(self._version_2_message(), sig_b),
            clock=lambda: FIXED_CLOCK,
        )
        assert reason_of(result) == INPUT_MISMATCH, (
            "VECTOR 3 CASE B: a valid signature over the version-2 message, "
            "submitted to a verifier whose reconstruction begins 00 31 00, "
            f"differs at offset 34 and is refused at V5 (L1412-1420); got "
            f"{reason_of(result)}"
        )

    def test_obligation_22e_vector_4_case_a_signature_refuses_first(self):
        requires("regression")
        raw = vector_mapping(VECTOR_1_MAPPING_TEXT)
        sig_a = proof_for("ai-03", raw)["signature"]
        result = admit(
            raw,
            producer_proof=proof_with(self._altered_tag_message(), sig_a),
            clock=lambda: FIXED_CLOCK,
        )
        assert reason_of(result) == SIGNATURE_INVALID, (
            "VECTOR 4 CASE A: the altered-tag message carried with VECTOR 1's "
            f"signature does not verify (L1438-1439); got {reason_of(result)}"
        )

    def test_obligation_22f_vector_4_case_b_reconstruction_refuses(self):
        requires("regression")
        from trust_harness import _private

        raw = vector_mapping(VECTOR_1_MAPPING_TEXT)
        sig_b = _private("ai-03").sign(self._altered_tag_message()).hex()
        result = admit(
            raw,
            producer_proof=proof_with(self._altered_tag_message(), sig_b),
            clock=lambda: FIXED_CLOCK,
        )
        assert reason_of(result) == INPUT_MISMATCH, (
            "VECTOR 4 CASE B: V5's reconstruction differs at offset 0, so the "
            f"submission is refused there (L1440-1443); got {reason_of(result)}"
        )


class TestCorrectivePatchRegressions:
    """Two regressions found by architecture review of PR #87.

    Neither is one of §7.3.7's 22 obligations. They are defects in THIS change's
    own implementation of §7.3.6 rule 7 and §7.3.11's fail-closed startup, and
    they are kept beside the obligations so the same executions cover them.
    """

    def test_huge_integers_serialize_to_exact_decimal_bytes(self):
        """§7.3.6 rule 7: integers are plain decimal with ARBITRARY precision.

        CPython caps `str(int)` at `sys.get_int_max_str_digits()` (4300 by
        default) and raises `ValueError` past it, so a legally supplied integer
        could have become an unserializable value. The expected bytes are built
        from the number's STRUCTURE and never from `str(huge)`, which would hit
        the same cap in the test.
        """
        import sys

        from plugins.evidence.signed_input import (
            canonical_serialization,
            signed_input,
        )

        exponent = 5000
        huge = 10**exponent + 123
        expected_digits = "1" + "0" * (exponent - 3) + "123"
        assert len(expected_digits) == exponent + 1
        limit = sys.get_int_max_str_digits()
        if limit:
            assert len(expected_digits) > limit, (
                "this regression is about integers past the interpreter's "
                f"decimal-conversion limit; {len(expected_digits)} digits does "
                f"not exceed {limit}"
            )

        # Small values first, including a base-10**9 chunk boundary.
        assert canonical_serialization(0) == b"0"
        assert canonical_serialization(7) == b"7"
        assert canonical_serialization(-7) == b"-7"
        assert canonical_serialization(10**9) == b"1000000000"
        assert canonical_serialization(10**9 + 1) == b"1000000001"

        assert canonical_serialization(huge) == expected_digits.encode("ascii")
        assert canonical_serialization(-huge) == (
            "-" + expected_digits
        ).encode("ascii")

        mapping = {"n": huge}
        expected_object = b'{"n":' + expected_digits.encode("ascii") + b"}"
        assert canonical_serialization(mapping) == expected_object

        prefix = bytes.fromhex(VECTOR_PREFIX_HEX)
        assert signed_input(mapping) == prefix + expected_object, (
            "the signed input is the fixed domain-separated prefix followed by "
            "exactly those canonical bytes (§7.3.4)"
        )

    def test_deeply_nested_configuration_fails_closed(self, monkeypatch):
        """§7.3.11: a configuration the parser cannot read is INVALID, not fatal.

        The reader must not fail to import: the package imports it, so an
        escaping `RecursionError` would turn a deployment misconfiguration into
        an ImportError instead of the REJECTED outcome §7.3.8 defines.

        THE TRIGGER IS A CONTROLLED DOUBLE, not a deep document. Measured on
        this interpreter, `json.loads` of `"[" * 1100 + "]" * 1100` does NOT
        raise even though the Python recursion limit is 1000: the C scanner
        recurses on a SEPARATE C-stack budget that `sys.setrecursionlimit()`
        does not expose, so the depth that triggers it is not derivable from
        anything the test can query. A document-based trigger would therefore be
        environment-dependent — and a case that "passed" because the parse
        merely returned a non-object would be testing nothing. The double below
        makes the parser raise exactly the exception this regression is about,
        deterministically, while leaving `producer_auth`'s own handler, the real
        `json` module and the process's trust state untouched.
        """
        from plugins.evidence import producer_auth

        class _RecursingParser:
            """Stands in for `json` ONLY in producer_auth's namespace."""

            @staticmethod
            def loads(*args, **kwargs):
                raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(producer_auth, "json", _RecursingParser)

        state = producer_auth._build_state('{"collision_policy": "A"}')
        assert state is producer_auth._INVALID, (
            "a configuration whose parse overruns the recursion limit must leave "
            "the reader in the same unusable state every other malformed "
            f"configuration leaves it in; got {state!r}"
        )
