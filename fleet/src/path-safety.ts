import path from "node:path";

export type PathStyle = "win32" | "posix";

export interface ContainmentResult {
  contained: boolean;
  reason: string | null;
  style: PathStyle;
  root: string;
  candidate: string;
  resolved_root: string;
  resolved_candidate: string;
  relative: string;
}

export interface SanitizedPath {
  ok: boolean;
  path: string | null;
  reason: string | null;
}

const WINDOWS_RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i;
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
const DRIVE_PREFIX = /^[A-Za-z]:/;
const UNC_PREFIX = /^[/\\]{2}/;

export function detectPathStyle(root: string): PathStyle {
  if (DRIVE_PREFIX.test(root) || UNC_PREFIX.test(root) || root.includes("\\")) {
    return "win32";
  }
  return "posix";
}

function pathModule(style: PathStyle): typeof path.win32 | typeof path.posix {
  return style === "win32" ? path.win32 : path.posix;
}

function hasAdsSegment(value: string, style: PathStyle): boolean {
  if (style !== "win32") {
    return false;
  }
  const withoutDrive = value.replace(DRIVE_PREFIX, "");
  return withoutDrive.includes(":");
}

export function checkContainment(root: string, candidate: string): ContainmentResult {
  const style = detectPathStyle(root);
  const pathMod = pathModule(style);
  const empty: ContainmentResult = {
    contained: false,
    reason: "empty",
    style,
    root,
    candidate,
    resolved_root: "",
    resolved_candidate: "",
    relative: ""
  };
  if (root.length === 0 || candidate.length === 0) {
    return empty;
  }
  if (root.includes("\u0000") || candidate.includes("\u0000")) {
    return { ...empty, reason: "nul" };
  }
  if (hasAdsSegment(candidate, style)) {
    return { ...empty, reason: "ads" };
  }
  const resolvedRoot = pathMod.resolve(root);
  const resolvedCandidate = pathMod.isAbsolute(candidate)
    ? pathMod.resolve(candidate)
    : pathMod.resolve(resolvedRoot, candidate);
  const compareRoot = style === "win32" ? resolvedRoot.toLowerCase() : resolvedRoot;
  const compareCandidate = style === "win32" ? resolvedCandidate.toLowerCase() : resolvedCandidate;
  const relative = pathMod.relative(compareRoot, compareCandidate);
  const contained =
    relative === "" ||
    (!relative.startsWith(`..${pathMod.sep}`) &&
      relative !== ".." &&
      !pathMod.isAbsolute(relative));
  return {
    contained,
    reason: contained
      ? null
      : pathMod.isAbsolute(candidate)
        ? "absolute-outside-root"
        : "outside-root",
    style,
    root,
    candidate,
    resolved_root: resolvedRoot,
    resolved_candidate: resolvedCandidate,
    relative
  };
}

export function sanitizeRelativePath(input: unknown): SanitizedPath {
  if (typeof input !== "string") {
    return { ok: false, path: null, reason: "not-string" };
  }
  if (input.length === 0) {
    return { ok: false, path: null, reason: "empty" };
  }
  if (input.length > 512) {
    return { ok: false, path: null, reason: "too-long" };
  }
  if (input.includes("\u0000") || CONTROL_CHARS.test(input)) {
    return { ok: false, path: null, reason: "control-character" };
  }
  const normalizedSeparators = input.replaceAll("\\", "/");
  if (normalizedSeparators.startsWith("/")) {
    return { ok: false, path: null, reason: "absolute" };
  }
  if (DRIVE_PREFIX.test(normalizedSeparators)) {
    return { ok: false, path: null, reason: "drive" };
  }
  if (normalizedSeparators.startsWith("//")) {
    return { ok: false, path: null, reason: "unc" };
  }
  const segments = normalizedSeparators.split("/");
  for (const segment of segments) {
    if (segment.length === 0) {
      return { ok: false, path: null, reason: "empty-segment" };
    }
    if (segment === "." || segment === "..") {
      return { ok: false, path: null, reason: "dot-segment" };
    }
    if (segment.includes(":")) {
      return { ok: false, path: null, reason: "ads" };
    }
    if (segment.endsWith(".") || segment.endsWith(" ")) {
      return { ok: false, path: null, reason: "windows-trailing" };
    }
    if (WINDOWS_RESERVED.test(segment)) {
      return { ok: false, path: null, reason: "windows-reserved" };
    }
  }
  return { ok: true, path: segments.join("/"), reason: null };
}

export function isSafeReference(value: string): boolean {
  return sanitizeRelativePath(value).ok;
}

export function isSafeArtifactRef(value: string): boolean {
  return isSafeReference(value);
}
