# CP-A_V3_FINAL_REPORT

Execution record for CP-A v3.0 — from rebaseline to PR-ready.

Coordinator: project execution coordinator + adversarial reviewer.
Implementation agent: Claude CLI (drafting only; no architecture judgement).

---

## A. Baseline

```text
origin/main = 34a685b5ae5885fb2a496f88af0ff422af2f5894
    verified by git fetch origin --prune on 2026-10-13; PR #99 is the last
    merge; no later commit exists.

branch        docs/cp-a-v3-decision-packet, created FROM 34a685b5
              (merge-base verified = 34a685b5)

superseded    the v2.x packet drafts' baseline a0bf12ba (merge of PR #97),
              which predates PR #98 (AI-15 PR-1: five phase amendments, the
              obligation-18 restructure) and PR #99 (AI-15 PR-2: the §7.3.13
              connection-change verification module). The string "a0bf12ba"
              appears NOWHERE in the v3.0 packet (grep-verified).

post-baseline contract state the packet is built against (all merged by
PR #98, merge commit 285d5c9e836d3f5f79903d59fc29070707705d6a, head
a731c501ff8ae8d4a992d9191dea950385eba847, 2026-10-12):
    AI-05 Amendment 9   §7.3.13 exact approved call-site set (FROZEN)
    AI-06 Amendment 2   §15.8 production-side signing boundary (FROZEN)
    AI-08 Amendment 5   submission-envelope pass-through
    AI-14 Amendment 5   the B5 joint-delivery rules
    AI-15 Amendment 7   §7.2 quotation corrected; §17.2d third-party row
plus PR #99 (34a685b5): tests/evidence/connection_change_verification.py +
callsite_identity.py (layer1, in CI).
```

## B. Files changed

This PR contains exactly **two new files**. **No tracked file is modified** —
no contract, no test, no workflow (git diff vs 34a685b5 is empty of tracked
changes).

| File | Content |
|---|---|
| `docs/CP-A_DECISION_PACKET/CP-A_DECISION_PACKET_v3.0.md` | the decision packet (1197 lines) |
| `docs/CP-A_DECISION_PACKET/CP-A_V3_FINAL_REPORT.md` | this report |

Local working artifacts deliberately NOT in the PR (untracked, unpublished):
the four superseded v2.x drafts (`PROJECT_OWNER_DECISION.md`,
`AI14_OWNER_DECISION.md`, `AI05_OWNER_DECISION.md`, `CP-A_STATUS.md`), the
drafting spec (`CP-A_V3_SPEC.md`), and the two pre-v3.0 audit reports
(`CP-A_TRAE_INDEPENDENT_REVIEW.md`, `CP-A_TRAE_REBASE_AUDIT.md`). Their
disposition is the requester's; the v3.0 packet's CLOSED HISTORY section is
self-contained and cites the closing amendments, not the drafts.

## C. Closed / open matrix

### CLOSED — CLOSED_BY_PHASE_AMENDMENT (no reopening; recorded in packet §2)

| v2.x item | Closed by | Evidence |
|---|---|---|
| D1 — joint-delivery mechanism | AI-14 Amendment 5(c) | PR #98, merge `285d5c9e…` (in-tree :1521-1556; corroborated by AI-15 Amendment 7's §17.2d third row) |
| C1 — persist vs `admit_to_store` | AI-14 Amendment 5(a) | PR #98 (in-tree :1314-1330) |
| C2 — §22.1 ORDER scope | AI-14 Amendment 5(b) | PR #98 (in-tree :1355-1363) |
| C3a — third-party (AI-05) row | AI-14 Amendment 5(c) | PR #98 (in-tree :1531-1534, :1551-1556) |
| C3b — §7.2 quotation sync request | AI-15 Amendment 7 | PR #98 (in-tree :1034-1042) — the request's subject no longer exists |
| C4 — §24 vs same-merge rule | AI-14 Amendment 5(d) | PR #98 (in-tree :1744-1757) |
| D2 — §7.3.7 writer-absence obligation disposition | AI-05 Amendment 9 (§7.3.13) | PR #98 (obligation-18 restructure, `APPROVED_CALL_SITES` :1243) + PR #99 (`34a685b5…`, connection-change verification). The old four-field authorisation model is DELETED, not redesigned. |

### OPEN — DECISION REQUIRED (packet §3; question + facts + decision scope only; no choice made)

| Item | Subject | Owner(s) | Structural notes |
|---|---|---|---|
| D3 | First target event | project owner | recommendation kept, labelled "not a decision"; unresolved-matters list refreshed (U1/U4 resolved) |
| D4 | Trust configuration owner | project owner | facts re-verified |
| D5 | `ai-06` key custody | project owner | facts re-verified |
| D6 | `AdmissionOutcome` propagation | implementing party AND AI-14 owner | dual signature records; one signature alone decides nothing |
| D7 | Status-document synchronisation | project owner | conflict inventory REGENERATED at 34a685b5 (4 live conflicts incl. the new AI-15 internal `## Status` SIX-vs-SEVEN divergence and the two-author residue at :3398/:2750/:3099; 3 v2.x conflicts marked resolved and excluded) |
| D8 | Joint integration acceptance owner | project owner | remit excludes AI-14's STEP 3 classification |
| N1 | AI-06 §15.8 signing-helper delivery | project owner (deferral path: AI-06 owner) | Reading 1 / Reading 2 stated neutrally; contract tension recorded; NO early choice |
| N1-C | Conditional action under N1 | AI-14 owner (if it arises) | subsection of N1, NOT a register item, NOT a gate, exists only under Reading 1, no signature box of its own |
| N3 | `store.write` acceptance assertion | AI-05 owner (joint review applies) | the rule-vs-check gap from the connection-safety audits |
| N4 | AI-15 §20 fourth same-change surface | AI-15 contract maintainer + project owner | §8.3 condition 2's second naming surface |

Out of scope, untouched: AI15-OPEN-3 (AI-04), AI15-OPEN-4 (AI-13/AI-14),
AI-11 §21.1 OPEN-1, AI-05 §35.1, AI-12-C.

## D. Validation results

```text
1. ADVERSARIAL REVIEW (coordinator, STEP 2)
   one defect found and fixed:
     - the §4 delivery-matrix row "AI-05 compatibility delivery" claimed
       "NOT BLOCKED ON ANY OPEN DECISION" while register item N3 decides
       whether that acceptance part gains the store.write assertion.
       Fixed to "NOT BLOCKED ON ANY CLOSED ITEM — content pending N3" with
       the N3 dependency in the precondition cell. Fix verified by direct
       re-read of the row and a full grep-battery re-run on the final file.
   checked clean: no contract modification; no decision language; no OPEN
   item prematurely closed; evidence sufficient (see item 7).

2. MARKDOWN CONSISTENCY CHECK        PASS
   1197 lines; 0 trailing whitespace; 74 code fences balanced; no heading
   level jumps; every table block has constant pipe count and a well-formed
   separator row; no TAB characters; valid UTF-8.

3. GIT DIFF REVIEW                   PASS
   merge-base(HEAD, 34a685b5) = 34a685b5; zero tracked-file modifications;
   the only PR content is the two new files in B.

4. GREP — OLD BASELINE               PASS
   "a0bf12ba" in the v3.0 packet: 0 occurrences.

5. GREP — OLD D2 MODEL               PASS
   "expected_call_count" / "enclosing_function" / "DRAFT E" / "DRAFT F" /
   "D2.3-GRANULARITY": 0 occurrences. "four-field": exactly 1 occurrence —
   the rule-mandated deletion record ("the old four-field authorisation
   model ... is DELETED and is NOT redesigned here").

6. DECISION LANGUAGE                 PASS
   "owner decides" / "must implement" / "shall choose" / "the answer is" /
   "Reading 1 is correct" / "CP-A adopts": 0 occurrences. 41 unchecked
   decision boxes; 27 "DECISION REQUIRED" mentions; "CP-A v3.0 = NOT
   SATISFIED" stands.

7. CITATION SPOT-CHECKS (coordinator, against the current tree)
   verified correct, among others: AI-15 §7.4 :1155-1156; §8.3 conditions
   8/9/10 at :1213/:1218-1219/:1220; §7.3 T2 :1076-1079; §5.2 :796-797;
   §20 appendix :4887 and §20.7 :4976-4985; the D7 second-instance
   two-author residues at :3398, :2750, :3099; AI-06 §15.8's eight tests
   :1210-1226 and the "UNTIL THOSE TESTS" clause :1228-1229; AI-05 §7.3.8
   :1680, §7.3.9 :1784, §7.3.12 :2307, §7.3.7's replaced obligation
   :1659-1665, §7.3.13 standard :2368; models.py:143-150;
   layer0_policy.py:3583. Claude reported zero unverifiable citations; the
   coordinator independently re-verified the load-bearing subset above.

8. IMPLEMENTATION-AGENT EXECUTION NOTE
   two Claude CLI invocations were used (initial draft; one targeted fix).
   Both completed their edits but exited non-zero on local environment
   errors (an unrecognized model configuration and sandbox denial of
   ~/.claude session-file writes) — in the second invocation the fix landed
   via the session's background completion after the error. Every artifact
   was therefore independently re-verified by the coordinator on its final
   state (full read, structure grep, and the complete battery in items
   2-6 re-run after the last file modification).
```

## E. Remaining UNKNOWN

```text
1. N2 — named in the v2.4 review scope, absent from every artifact in this
   repository, and never defined. It is NOT carried into v3.0. If it denotes
   a live question, its content must be supplied by the requester before
   any signature round.

2. The "v2.4" artifact itself — the packet the earlier review scopes
   described (with N1/N1-C/N2 as register items) was never found on disk.
   v3.0 was built from the on-disk v2.x drafts plus the requester's
   confirmed definitions of N3 and N4; N1/N1-C were reconstructed from the
   AI-06 §15.8 context of those review scopes.

3. D2 residual observation (recorded, not raised as an item — the
   migration rules close D2 without redesign): the counts recorded in
   AI-05 Amendment 7 (d), §35.3 and `## Status` predate the PR #98/#99
   node/test restructure. Reconciling them is AI-05's owner's housekeeping
   under AI-05 §34; D7.1's inventory already captures the AI-15-side count
   divergence. No action is requested here.

4. Signature state — all 41 decision boxes are unsigned by design. CP-A
   v3.0 = NOT SATISFIED until every OPEN item carries a signed conclusion
   with decider, date, reason and contract. D6 requires both signatures on
   the same option.

5. The v2.x drafts' disposition — they remain local and untracked. Whether
   to archive, publish or discard them is the requester's; this PR neither
   publishes nor deletes them.
```

---

**Final state: PR OPEN, awaiting human review. Not to be merged without it.**
