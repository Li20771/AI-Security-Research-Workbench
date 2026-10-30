import { test } from "node:test";
import assert from "node:assert/strict";
import {
  checkContainment,
  isSafeReference,
  sanitizeRelativePath
} from "../src/path-safety.ts";

test("ordinary relative paths are accepted", () => {
  for (const path of ["notes.txt", "reports/report-1.md", "artifacts/run-1/out.txt", "a/b/c"]) {
    const result = sanitizeRelativePath(path);
    assert.equal(result.ok, true, path);
    assert.equal(result.path, path);
  }
});

test("traversal and platform-specific escapes are rejected without touching the filesystem", () => {
  const cases = [
    "../etc/passwd",
    "..\\Windows\\win.ini",
    "a/../../b",
    "/etc/passwd",
    "\\Windows\\win.ini",
    "C:\\Windows\\win.ini",
    "\\\\server\\share\\file",
    "notes.txt\u0000",
    "notes.txt:stream",
    "CON",
    "con.txt",
    "NUL",
    "COM1",
    "trailing.",
    "trailing ",
    "a//b",
    "./a",
    ""
  ];
  for (const candidate of cases) {
    const result = sanitizeRelativePath(candidate);
    assert.equal(result.ok, false, JSON.stringify(candidate));
  }
  assert.equal(isSafeReference("reports/report-1.md"), true);
  assert.equal(isSafeReference("../outside"), false);
});

test("win32 containment is lexical and case-insensitive", () => {
  const root = "D:\\lab\\ws_a";
  assert.equal(checkContainment(root, "notes.txt").contained, true);
  assert.equal(checkContainment(root, "reports/report-1.md").contained, true);
  assert.equal(checkContainment(root, "d:\\LAB\\WS_A\\notes.txt").contained, true);
  assert.equal(checkContainment(root, "..\\ws_b\\secret.txt").contained, false);
  assert.equal(checkContainment(root, "C:\\Windows\\win.ini").contained, false);
  assert.equal(checkContainment(root, "D:\\lab\\ws_a2\\notes.txt").contained, false);
  const escape = checkContainment(root, "..\\ws_b\\secret.txt");
  assert.equal(escape.reason, "outside-root");
  assert.equal(escape.resolved_root.length > 0, true);
});

test("posix containment works without assuming Windows", () => {
  const root = "/srv/lab";
  assert.equal(checkContainment(root, "reports/report-1.md").contained, true);
  assert.equal(checkContainment(root, "/srv/lab/reports/report-1.md").contained, true);
  assert.equal(checkContainment(root, "../etc/passwd").contained, false);
  assert.equal(checkContainment(root, "/srv/lab2/report").contained, false);
  assert.equal(checkContainment(root, "/etc/passwd").contained, false);
});

test("containment rejects NUL and ADS-style candidates", () => {
  const root = "D:\\lab\\ws_a";
  assert.equal(checkContainment(root, "notes.txt\u0000").contained, false);
  assert.equal(checkContainment(root, "notes.txt:stream").contained, false);
});
