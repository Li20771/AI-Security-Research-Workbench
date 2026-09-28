# AI-01 — DSH Baseline Checkpoint #8: Permission Boundary Test

> **Status: COMPLETE — CHECKPOINT #8**
> Experiment ID: `AI-01-DSH-20260928-008`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 · CP6 · CP7 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Objective

Resolve AI-01 exit criterion #9:

> **Permission boundaries verified** — required evidence: *allowed + blocked cases*

CP5 recorded #9 as `BLOCKED` for one specific reason: **a blocked case existed but no allowed
case did.** This checkpoint set out to obtain a real, executed `ALLOWED` case to pair with it.

Both cases below are **executed**, not inferred. Nothing here is derived from CP6's
`自动授权审查实验性 = 已开`, from a plugin toggle, or from the existence of any plugin.

## 2. Baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp8` |
| Base SHA | `dd06c9b10df71d9ba1f2271a77567f815498f31e` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree | clean |
| DSH version | `0.1.7-rc.2` |
| DSH run | 5 processes, started `2026-09-28 10:32:20` |
| Test executed | `2026-09-28 19:25–19:26` (local) |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |

## 3. Permission model under test

**DSH's native network-exposure boundary**, established by the configured setting

```yaml
dsh-desktop:
  networkExposure: loopback
```

This is the only DSH-native access-control boundary that is *configured*, *observable*, and
*enforced* on this installation. CP4 §6.2 established that **no** permission/guard/policy
configuration exists anywhere else in DSH.

The model under test is therefore a **reachability/access boundary**: which clients are
permitted to reach the DSH service at all.

```text
subject  = a client attempting to reach the DSH HTTP service on port 19387
policy   = loopback only
question = is the client permitted to reach the service?
```

**A separate boundary — authentication (`401`) — is also observed below and is reported
separately**, because it produces blocked evidence only (see §8).

## 4. Test environment and test object

| Item | Value |
| --- | --- |
| Test object | DSH's own loopback HTTP endpoint, `127.0.0.1:19387` |
| Client | `curl` and a raw `TcpClient`, run from this host |
| Isolation | localhost only; no remote resource contacted |
| Scratch workspace used | **NO** — not required (see §5) |
| SecurityLab contacted | **NO** |
| System directories touched | **NO** |
| Credentials / tokens touched | **NO** |
| Configuration mutated | **NO** |

The test object is the DSH service itself, reached only over loopback. It is fully isolated
from SecurityLab, system directories, credential stores, and remote resources.

## 5. Pre-test configuration — and why no scratch workspace was needed

The task set two priorities: **first** find a token-free `ALLOWED` path, **and only if that
fails**, construct a scratch workspace.

**Priority 1 succeeded**, so priority 2 was not exercised and **no DSH configuration was
changed at all**:

| Step | Result |
| --- | --- |
| Configuration modified for this test | **NO** |
| SecurityLab workspace entry touched | **NO** |
| Restoration required | **NO** |

The task listed *"允许的 localhost 操作"* explicitly as an acceptable `ALLOWED` case, and that
is exactly what §6 supplies.

> Note: constructing a *filesystem* permission case would have required the DSH agent surface
> (GUI or token) plus a configuration mutation. Since priority 1 succeeded, that was neither
> needed nor attempted. Its absence is recorded as a limitation in §12.

## 6. Case A — ALLOWED (executed)

### 6.1 Input

```text
A1:  curl -s -i http://127.0.0.1:19387/
A2:  curl -s -o /dev/null -w "%{http_code} %{remote_ip}" http://localhost:19387/
A3:  curl -s http://127.0.0.1:19387/api/plugins
A4:  curl -s http://127.0.0.1:19387/health          # route-absent control
```

### 6.2 Expected

```text
The loopback client is permitted to reach the service: the TCP connection
completes and DSH processes the request and returns an HTTP response.
```

### 6.3 Actual

```text
A1:  HTTP/1.1 401 Unauthorized
     cache-control: no-store
     content-type: text/plain; charset=utf-8
     Date: Mon, 28 Sep 2026 11:25:27 GMT
     Connection: keep-alive
     Transfer-Encoding: chunked
     <body: "dsh web authentication required; ...">

A2:  http_code=401  remote_ip=127.0.0.1  connect=0.203503s
A3:  connect completed, http_code=401
A4:  http_code=404
```

The decisive observations:

- the **TCP connection completes** on loopback — the client is not refused;
- DSH **generates and returns a complete HTTP response** (status line, headers, body);
- the request **reaches the application and is routed** — the service distinguishes an
  auth-gated route (`/api/plugins` → `401`) from an absent route (`/health` → `404`),
  which only a processed request can produce.

A transport-level refusal could not produce any of these. The loopback client is
**permitted to reach and interact with the service**.

### 6.4 Status

```text
Case A  expected = allowed
        actual   = the operation succeeded — connection accepted, request
                   processed and routed, complete HTTP response returned

        STATUS   = PASS
```

## 7. Case B — BLOCKED (executed)

### 7.1 Input

```text
B1:  curl http://172.24.208.1:19387/     # Hyper-V/WSL vEthernet
B2:  curl http://10.17.167.58:19387/     # primary LAN address
B3:  curl http://169.254.50.200:19387/   # link-local
B4:  curl http://169.254.90.203:19387/   # link-local
B5:  curl http://169.254.24.85:19387/    # link-local
B6:  curl http://[::1]:19387/            # IPv6 loopback
B7:  raw TcpClient.Connect('10.17.167.58', 19387)

Authoritative scope check:
     Get-NetTCPConnection -State Listen | where OwningProcess in DSH PIDs
```

### 7.2 Expected

```text
The same operation, originating from any non-loopback interface, is refused:
no connection is possible, because DSH listens on loopback only.
```

### 7.3 Actual

```text
B1  http://172.24.208.1:19387    -> code=000  curl_exit=7
B2  http://10.17.167.58:19387    -> code=000  curl_exit=7
B3  http://169.254.50.200:19387  -> code=000  curl_exit=7
B4  http://169.254.90.203:19387  -> code=000  curl_exit=7
B5  http://169.254.24.85:19387   -> code=000  curl_exit=7
B6  http://[::1]:19387           -> code=000  curl_exit=7
B7  raw TCP -> "target machine actively refused the connection"

Listening scope (every non-loopback interface tested):
     LocalAddress   LocalPort
     127.0.0.1      19387          <- the ONLY listener
```

`curl_exit=7` is *failed to connect*. **Every one of the six address families/interfaces was
refused**, and the authoritative scope check shows DSH has exactly one listener, bound to
`127.0.0.1`.

The IPv6 result is notable: `::1` is loopback, yet it is also refused — DSH binds the **IPv4**
loopback only.

### 7.4 Status

```text
Case B  expected = denied
        actual   = denied — connection refused on all six non-loopback targets,
                   and no non-loopback listener exists

        STATUS   = PASS
```

## 8. Separately: the authentication boundary

The `401` responses above belong to a **different** boundary — authentication — and are
reported separately so the two are not conflated.

| Direction | Evidence | Status |
| --- | --- | --- |
| **Blocked** — unauthenticated request denied | `401` on `/`, `/index.html`, `/api/health`, `/api/plugins`, `/api/workspace`, `/api/sessions`, `/api/auth/status`, `/api/version` | **PASS** (executed) |
| **Allowed** — an authenticated request succeeding | requires the **session token** | **NOT_RUN** (forbidden) |

A bounded search for a token-free allowed path on this boundary returned **none**: every
existing route is auth-gated (`401`), and every other path is `404` (route absent). There is
**no unauthenticated `200`** on this service, so the authentication boundary yields blocked
evidence only. **No attempt was made to authenticate, extract a token, or bypass the gate.**

## 9. Criterion #9 — classification

```text
Criterion #9  Permission boundaries verified

  CP4: BLOCKED   CP5: BLOCKED   CP6: BLOCKED   CP7: BLOCKED
  CP8: PASS      (scope: §9.2)
```

CP5's recorded blocker was: *"the required evidence is 'allowed + blocked' and no **allowed**
case exists."* An allowed case now exists and was executed. The blocker is resolved for the
boundary that is actually configured, observable, and enforced.

### 9.1 Basis

| Case | Expected | Actual | Status |
| --- | --- | --- | --- |
| **A — ALLOWED** | loopback client permitted | connection accepted, request processed and routed, complete HTTP response returned | **PASS** |
| **B — BLOCKED** | non-loopback client refused | refused on all six non-loopback targets; single listener on `127.0.0.1` | **PASS** |

### 9.2 Scope of this PASS — what it does and does not cover

**Covered.** DSH's native network-exposure boundary is verified in both directions by
execution: loopback clients are permitted to reach and be served by the DSH service, and
non-loopback clients are refused.

**Not covered, and not claimed:**

1. **The allowed side of the authentication boundary** — requires the session token
   (forbidden). Blocked side only (§8).
2. **A filesystem / workspace permission case** — `NOT_RUN`. No such configuration exists in
   DSH (CP4 §6.2), and exercising it needs the DSH agent surface (GUI or token) plus a
   configuration mutation, which priority 1 made unnecessary.
3. **Any agent-tool permission model** — the read / analyze / test / modify / system-change /
   remote-change ladder of AI-00 §6 is **not implemented in DSH**. It is Guard's job (AI-04),
   explicitly out of AI-01 scope.

> **This PASS must not be read as "DSH enforces an agent permission model."** DSH does not
> have one today. What is verified is the access boundary DSH actually has.
>
> **`自动授权审查实验性 = 已开` (CP6) was NOT used as evidence here**, per the standing rule.
> A toggle is not enforcement; a plugin's existence is not enforcement.

## 10. Restoration

| Item | Result |
| --- | --- |
| Configuration changed for this test | **NO** |
| Restoration required | **NO — not applicable** |
| Configuration verified unchanged after the test | **YES** — no DSH file was written |

No scratch workspace was created, so there is nothing to restore and nothing that could have
leaked into the existing SecurityLab workspace configuration.

## 11. Integrity

| Invariant | Result |
| --- | --- |
| SecurityLab unchanged | **PASS** — `main` @ `efa836ff9225f6226ca8a76615f3f45c31110d58`, `git status --short` empty (0 files) |
| SecurityLab **not** used as a probe target | **PASS** — never contacted |
| Workbench `main` unchanged | **PASS** — work on a branch |
| Workbench production code unchanged | **PASS** — documentation only |
| `PROJECT_STATUS.md` unchanged | **PASS** |
| DSH configuration unchanged | **PASS** — no file written; no process action |
| DSH unaffected | **PASS** — 5 processes, same PIDs `24404, 29052, 29320, 38716, 43500`, same start `2026-09-28 10:32:20` |
| **Token / credential safety** | **PASS** — session token never obtained, read, printed, copied or used; `~/.dsh/.credentials.yaml` never opened; no password or API key accessed |
| No auth bypass attempted | **PASS** — only unauthenticated requests were sent, and they were denied |
| No system directory, remote resource or vehicle network touched | **PASS** |
| No Guard / plugin implemented | **PASS** |
| No AI-02 work started | **PASS** |

## 12. Known limitations

Inherited from CP1 §9.2, CP3 §7.2, CP4 §9 (11–16), CP5 §11 (17–18), CP6 §9 (19–24),
CP7 §8 (25–27) — all still open. Added at this checkpoint:

28. **#9's PASS covers the network-exposure boundary only** (§9.2). The authentication
    boundary has blocked evidence only, and no filesystem/agent permission case was run.
29. **There is no agent permission model in DSH to test.** The AI-00 §6 ladder is unimplemented;
    until Guard exists (AI-04) this cannot be verified in DSH, and its absence is not a DSH defect.
30. **A filesystem permission case remains `NOT_RUN`** and would require the DSH agent surface
    plus a reversible configuration mutation — deliberately not attempted while priority 1 held.
31. **The `169.254.x` targets are link-local and may be transient**, and `172.24.208.1` is a
    virtual adapter. The blocked result is nonetheless corroborated by the authoritative
    listener-scope check (one listener, `127.0.0.1`), which does not depend on those addresses.

## 13. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `dd06c9b10df71d9ba1f2271a77567f815498f31e` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard dd06c9b10df71d9ba1f2271a77567f815498f31e` |
| Side effects on DSH | **None** — no DSH state modified |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 14. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | the branch base `dd06c9b10df71d9ba1f2271a77567f815498f31e` at validation time, since the document was still uncommitted while these commands ran |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_8.md` |

## 15. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-008` |
| Checkpoint | #8 |
| Branch | `baseline/ai-01-dsh-20260928-cp8` |
| Base SHA | `dd06c9b10df71d9ba1f2271a77567f815498f31e` |
| Permission mechanism tested | DSH native network-exposure boundary (`networkExposure: loopback`) |
| Scratch workspace used | **NO** |
| Case A (ALLOWED) | expected `allowed` / actual **succeeded** / **PASS** |
| Case B (BLOCKED) | expected `denied` / actual **denied** / **PASS** |
| Configuration changed | **NO** |
| Configuration restored | **N/A** (nothing changed) |
| **Criterion #9** | **PASS** — scope per §9.2 |
| Criterion #3 | BLOCKED (unchanged) |
| Criterion #8 | PASS (unchanged) |
| **AI-01** | **BLOCKED** — #3 remains the sole blocker |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |

AI-01 is not complete: criterion #3 (clean installation) remains `BLOCKED` from CP7. This
checkpoint closes #9 only, and only within the scope stated in §9.2.
