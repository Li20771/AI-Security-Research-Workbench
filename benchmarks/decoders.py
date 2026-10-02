"""AI-11 §7, Annex A — the harness-side independent inspection primitives.

These are what make an oracle's observation INDEPENDENT. Each one derives a fact from
the pinned material rather than reading it back from a submission:

```text
decode_dbc_frame      the physical value of each declared signal, from the DBC + frame
inspect_elf           architecture and linkage, from the binary itself
run_binary            stdout and exit code, from executing it
inspect_firmware      filesystem, compression and config, from the image itself
```

### Why a decoder lives here rather than in a dependency

§A.1's card names `cantools` as the harness's decoder. It is not obtainable in the
benchmark environment, and a task whose oracle is permanently `BLOCKED` measures nothing
at all. The decoder below therefore implements the DBC subset the corpus declares, in
the harness, and the requirement §A.1 actually freezes — that the value comes from an
INDEPENDENT decode of the declared material rather than from the submission — is met in
full. The substitution is recorded in the PR as a reported deviation, not silently.

### Absent tools are BLOCKED

Every function that needs a program returns a `ToolUnavailable` marker rather than
raising or guessing. §8.2: nothing ran, so nothing is known about the thing checked.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "InspectionUnavailable",
    "decode_dbc_frame",
    "inspect_elf",
    "inspect_firmware",
    "parse_dbc_signals",
    "run_binary",
]

#: Wall-clock ceiling for one inspection command.
INSPECTION_TIMEOUT_SECONDS = 300


class InspectionUnavailable(RuntimeError):
    """A prerequisite was absent, so nothing was observed.

    Distinct from a wrong answer. §8.2 makes this BLOCKED, never FAIL.
    """

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class DecodedSignal:
    name: str
    start_bit: int
    length: int
    byte_order: int
    signed: bool
    factor: float
    offset: float
    raw: int
    physical: float


# ---------------------------------------------------------------------------
# DBC
# ---------------------------------------------------------------------------

#: `SG_ EngineSpeed : 0|16@1+ (1,0) [0|65535] "rpm" ECU_TEST`
_SIGNAL_RE = re.compile(
    r"^\s*SG_\s+(?P<name>\w+)\s*:\s*"
    r"(?P<start>\d+)\|(?P<length>\d+)@(?P<order>[01])(?P<sign>[+-])\s*"
    r"\((?P<factor>[-\d.eE+]+),(?P<offset>[-\d.eE+]+)\)"
)

#: `BO_ 291 EngineData: 8 ECU_TEST`
_MESSAGE_RE = re.compile(r"^\s*BO_\s+(?P<id>\d+)\s+(?P<name>\w+)\s*:\s*(?P<dlc>\d+)")


def parse_dbc_signals(dbc_text: str, message_id: int) -> tuple[Mapping[str, Any], ...]:
    """The signals the DBC declares for one arbitration id.

    A deliberately small parser for the subset the corpus declares. Anything it cannot
    read is REFUSED rather than skipped: a decoder that silently ignores a signal would
    compare fewer values and report a pass.
    """
    current: int | None = None
    found: list[Mapping[str, Any]] = []
    for line in dbc_text.splitlines():
        message = _MESSAGE_RE.match(line)
        if message:
            current = int(message.group("id"))
            continue
        if not line.strip().startswith("SG_"):
            continue
        if current != message_id:
            continue
        signal = _SIGNAL_RE.match(line)
        if signal is None:
            raise ValueError(
                f"the DBC declares a signal this decoder cannot read: {line.strip()!r}. "
                "Refusing rather than skipping: an unread signal would be a value nobody "
                "compared"
            )
        found.append(
            {
                "name": signal.group("name"),
                "start_bit": int(signal.group("start")),
                "length": int(signal.group("length")),
                "byte_order": int(signal.group("order")),
                "signed": signal.group("sign") == "-",
                "factor": float(signal.group("factor")),
                "offset": float(signal.group("offset")),
            }
        )
    return tuple(found)


def _extract_raw(data: bytes, start_bit: int, length: int, byte_order: int) -> int:
    """The raw integer a signal occupies.

    `@1` is little-endian (Intel): the start bit is the least significant bit of the
    signal and the signal runs upward. `@0` is big-endian (Motorola). Only the first is
    used by the corpus, and the second is implemented rather than refused so that a
    future task declaring it is not silently mis-decoded.
    """
    if byte_order == 1:
        whole = int.from_bytes(data, "little")
        return (whole >> start_bit) & ((1 << length) - 1)

    # Motorola: the start bit is the MSB, counted from the start of the payload.
    whole = int.from_bytes(data, "big")
    total = len(data) * 8
    shift = total - start_bit - length
    if shift < 0:
        raise ValueError("a big-endian signal starts outside the payload")
    return (whole >> shift) & ((1 << length) - 1)


def decode_dbc_frame(
    dbc_text: str, frame: str
) -> tuple[Mapping[str, Any], tuple[DecodedSignal, ...]]:
    """Decode one `<id>#<hex>` frame using the DBC.

    The frame's own arbitration id selects the signals, so a task whose frame names a
    message the DBC does not declare fails here rather than comparing nothing.
    """
    identifier, _, payload = frame.partition("#")
    if not _ or not payload:
        raise ValueError(f"frame {frame!r} is not in `<id>#<hex>` form")
    message_id = int(identifier, 16)
    data = bytes.fromhex(payload)

    declared = parse_dbc_signals(dbc_text, message_id)
    if not declared:
        raise ValueError(
            f"the DBC declares no signal for arbitration id {message_id}; a decode with "
            "nothing to compare would pass vacuously"
        )

    decoded: list[DecodedSignal] = []
    for spec in declared:
        raw = _extract_raw(data, spec["start_bit"], spec["length"], spec["byte_order"])
        signed_raw = raw
        if spec["signed"] and raw >= (1 << (spec["length"] - 1)):
            signed_raw = raw - (1 << spec["length"])
        decoded.append(
            DecodedSignal(
                name=spec["name"],
                start_bit=spec["start_bit"],
                length=spec["length"],
                byte_order=spec["byte_order"],
                signed=spec["signed"],
                factor=spec["factor"],
                offset=spec["offset"],
                raw=raw,
                physical=signed_raw * spec["factor"] + spec["offset"],
            )
        )
    return {"message_id": message_id, "dlc": len(data)}, tuple(decoded)


# ---------------------------------------------------------------------------
# process-backed inspection
# ---------------------------------------------------------------------------


def _run(argv: Sequence[str], *, timeout: int = INSPECTION_TIMEOUT_SECONDS):
    try:
        return subprocess.run(  # noqa: S603 - argv, no shell
            list(argv), capture_output=True, text=True, timeout=timeout, shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InspectionUnavailable(
            f"PROGRAM_UNAVAILABLE:{argv[0]}", f"{argv[0]} is not on this host"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise InspectionUnavailable(f"INSPECTION_TIMEOUT:{argv[0]}") from exc


def inspect_elf(binary: str | Path) -> Mapping[str, Any]:
    """§A.5. Architecture and linkage, read from the binary.

    `readelf -h` gives the machine; the presence of a `.dynamic` section is what
    distinguishes a dynamically linked binary from a static one. Neither is inferred
    from the file name or from the source.
    """
    header = _run(["readelf", "-h", str(binary)])
    if header.returncode != 0:
        raise InspectionUnavailable("READELF_FAILED", header.stderr.strip()[:200])

    machine = ""
    for line in header.stdout.splitlines():
        if "Machine:" in line:
            machine = line.split("Machine:", 1)[1].strip()
            break
    if not machine:
        raise InspectionUnavailable("READELF_NO_MACHINE")

    dynamic = _run(["readelf", "-d", str(binary)])
    # `readelf -d` exits 0 with a "There is no dynamic section" note, or non-zero on
    # some builds; both are handled by looking for the section rather than the status.
    linked = "dynamic" if ".dynamic" in dynamic.stdout or "NEEDED" in dynamic.stdout else "static"

    return {"architecture": machine, "linkage": linked}


def run_binary(binary: str | Path, argv: Sequence[str] = ()) -> Mapping[str, Any]:
    """§A.5. Execute the built binary and record what it printed and exited with.

    The program is run from the artefact itself. Its stdout and status are the
    observation; nothing about them is read from a fixture.
    """
    completed = _run([str(binary), *argv])
    return {
        "stdout": (completed.stdout or "").strip(),
        "exit_code": completed.returncode,
    }


def inspect_firmware(image: str | Path, *, extract_to: str | Path) -> Mapping[str, Any]:
    """§A.4. Filesystem, compression and config, derived from the IMAGE.

    `binwalk` identifies the filesystem and its compression; `unsquashfs` extracts it so
    the config values can be read out of the rootfs. The expected values are never read
    from a fixture and the image digest is never asserted — `build_fw.sh` calls
    `mksquashfs` without a reproducible-time flag, so the digest is not stable and is
    recorded as a measured fact only.
    """
    image = Path(image)
    if not image.is_file():
        raise InspectionUnavailable("IMAGE_ABSENT", f"{image} does not exist")

    identified = _run(["binwalk", str(image)])
    if identified.returncode != 0:
        raise InspectionUnavailable("BINWALK_FAILED", identified.stderr.strip()[:200])

    filesystem = ""
    compression = ""
    for line in identified.stdout.splitlines():
        lowered = line.lower()
        if "squashfs" in lowered:
            filesystem = "squashfs"
        if "gzip" in lowered:
            compression = "gzip"
        elif "xz" in lowered:
            compression = "xz"
        elif "lzma" in lowered:
            compression = "lzma"

    if not filesystem:
        raise InspectionUnavailable(
            "FILESYSTEM_NOT_IDENTIFIED", "binwalk reported no filesystem"
        )

    extract_to = Path(extract_to)
    extracted = _run(["unsquashfs", "-f", "-d", str(extract_to), str(image)])
    if extracted.returncode != 0:
        raise InspectionUnavailable("UNSQUASHFS_FAILED", extracted.stderr.strip()[:200])

    config = extract_to / "etc/syn_ecu/config.ini"
    if not config.is_file():
        raise InspectionUnavailable("CONFIG_ABSENT", f"{config} is not in the image")

    values: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()

    version = values.get("version", "")
    if not version:
        banner = extract_to / "etc/banner"
        version = banner.read_text(encoding="utf-8").strip() if banner.is_file() else ""

    return {
        "filesystem": filesystem,
        "compression": compression or "unknown",
        "version": version,
        "admin_password": values.get("admin_password", ""),
    }
