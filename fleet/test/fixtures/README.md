# Cross-repo MemoryPack v1.1 fixture

`memorypack.v1.1.dsh-memory.json` is a **synthetic** MemoryPack v1.1.0 pack
produced by the real `dsh-memory` producer, copied here unchanged so the
Workbench test suite can validate a producer output without a live cross-repo
connection or any network access.

- Producer repository: `dsh-memory`
- Producer base: `main` @ `4270b6886bf71804ac173155d60320c0c2f43d5c` plus the
  `fix/fleet-v3-round2-memory-hardening` working tree
- Producer command (from the dsh-memory repository root):
  `node tools/memorypack.fixture.mjs tools/fixtures/memorypack.v1.1.dsh-memory.json`
- Consumer test: `fleet/test/cross-repo-memorypack.test.ts`
- Contract: `docs/contracts/MEMORYPACK_V1_1.md` v1.1.0

The fixture exercises an approved `ws_a` / `ep_1` episode note, an approved
Unicode NFC path, an explicit `user-global` note owned by the reserved
`workspace_id: "global"`, a foreign `ws_b` note that must not appear, a pending
note, and an unmarked legacy note. Counts and
`policy.cross_workspace: true` are derived from that synthetic set.

Do not hand-edit the JSON. Regenerate it with the dsh-memory script and copy the
result here together with any expected-hash update in the Workbench test. It
contains no real vault, credential, provider, model or DSH data.
