const ENV_NAME = /^[A-Z_][A-Z0-9_]{0,63}$/;
const FORBIDDEN_FRAGMENTS = [
  "TOKEN",
  "SECRET",
  "PASSWORD",
  "CREDENTIAL",
  "API_KEY",
  "APIKEY",
  "AUTH",
  "PRIVATE_KEY",
  "ACCESS_KEY"
];

export function isForbiddenEnvName(name: string): boolean {
  const upper = name.toUpperCase();
  return FORBIDDEN_FRAGMENTS.some((fragment) => upper.includes(fragment));
}

export function filterEnvironment(
  allowlist: readonly string[],
  source: Readonly<Record<string, string>>
): Record<string, string> {
  const out: Record<string, string> = {};
  const seen = new Set<string>();
  for (const name of allowlist) {
    if (!ENV_NAME.test(name)) {
      throw new Error(`invalid environment name: ${name}`);
    }
    if (isForbiddenEnvName(name)) {
      throw new Error(`environment name is not permitted: ${name}`);
    }
    if (seen.has(name)) {
      continue;
    }
    seen.add(name);
    if (Object.hasOwn(source, name)) {
      const value = source[name];
      if (typeof value !== "string") {
        throw new Error(`environment value must be a string: ${name}`);
      }
      out[name] = value;
    }
  }
  return out;
}

export function environmentAllowlistNames(allowlist: readonly string[]): readonly string[] {
  return allowlist.filter((name) => ENV_NAME.test(name) && !isForbiddenEnvName(name));
}
