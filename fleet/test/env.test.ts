import { test } from "node:test";
import assert from "node:assert/strict";
import {
  environmentAllowlistNames,
  filterEnvironment,
  isForbiddenEnvName
} from "../src/env.ts";

test("only explicitly allowlisted environment names are copied, never secret-like names", () => {
  const source = {
    LANG: "en_US.UTF-8",
    TZ: "UTC",
    SECRET_TOKEN: "must-not-copy",
    DEEPSEEK_API_KEY: "must-not-copy",
    PATH: "must-not-copy"
  };
  const filtered = filterEnvironment(["LANG", "TZ"], source);
  assert.deepEqual(filtered, { LANG: "en_US.UTF-8", TZ: "UTC" });
  assert.equal(environmentAllowlistNames(["LANG", "SECRET_TOKEN"]).includes("SECRET_TOKEN"), false);
});

test("secret-like allowlist names are rejected instead of passed through", () => {
  assert.equal(isForbiddenEnvName("DEEPSEEK_API_KEY"), true);
  assert.equal(isForbiddenEnvName("API_TOKEN"), true);
  assert.equal(isForbiddenEnvName("LANG"), false);
  assert.throws(() => filterEnvironment(["API_KEY"], { API_KEY: "x" }));
  assert.throws(() => filterEnvironment(["lowercase"], { lowercase: "x" }));
});
