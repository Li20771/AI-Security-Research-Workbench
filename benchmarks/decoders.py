"""AI-11 §7, Annex A — the harness-side independent inspection primitives.

These are what make an oracle's observation INDEPENDENT. Each one derives a fact from
the pinned material rather than reading it back from a submission:

```text
decode_dbc_frame      the physical value of each declared signal, from the DBC + frame
inspect_elf           architecture and linkage, from the binary itself
run_binary            stdout and exit code, from executing it
inspect_firmware      filesystem, compression and config, from the image itself
```

### A.1's decoder is cantools, and there is no fallback

```text
FROZEN (A.1): the independent decoder is the harness's own cantools invocation.
```

`decode_dbc_frame` runs that invocation. There is **no native DBC decoder here** and
none is planned: a second decoder would be a different oracle wearing A.1's name, and a
reader comparing a run against the contract would have no way to tell which one produced
the numbers.

`cantools` is therefore a declared dependency of the benchmark suite
(`requirements-dev.txt`), so CI exercises the real A.1 path rather than only ever being
able to assert `BLOCKED`.

```text
cantools importable       the declared decoder runs
cantools absent           BLOCKED, with reason code CANTOOLS_UNAVAILABLE
```

An absent decoder is `BLOCKED` and never `FAIL`, and it is never worked around by a
substitute.

### Absent tools are BLOCKED

Every function that needs a program returns an `InspectionUnavailable` marker rather
than raising or guessing. §8.2: nothing ran, so nothing is known about the thing checked.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "InspectionUnavailable",
    "decode_dbc_frame",
    "inspect_elf",
    "inspect_firmware",
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


# ---------------------------------------------------------------------------
# DBC — A.1's declared decoder
# ---------------------------------------------------------------------------

#: The decoder program. It runs in a subprocess under the interpreter that is running
#: the harness, so it sees the same environment — and it either imports `cantools` or it
#: does not.
_CANTOOLS_PROGRAM = """
import json, sys
import cantools

database = cantools.database.load_file(sys.argv[1])
identifier, _, payload = sys.argv[2].partition("#")
message = database.get_message_by_frame_id(int(identifier, 16))
data = bytes.fromhex(payload)
decoded = message.decode(data)
units = {signal.name: signal.unit for signal in message.signals}
print(json.dumps({
    "message": message.name,
    "values": {name: float(value) for name, value in decoded.items()},
    "raw": {
        signal.name: int.from_bytes(
            data, "little"
        ) if signal.byte_order == "little_endian" else int.from_bytes(data, "big")
        for signal in message.signals
    },
    "units": units,
}))
"""


def decode_dbc_frame(
    dbc_path: str | Path, frame: str, *, runner: Any
) -> Mapping[str, Any]:
    """A.1. The harness's own `cantools` invocation, over the pinned DBC and the frame.

    ```text
    FROZEN (A.1): the independent decoder is the harness's own cantools invocation.
    ```

    There is no fallback decoder. If `cantools` is absent the task is BLOCKED, because a
    substitute would be a different oracle wearing A.1's name — and a reader comparing
    this run against the contract would have no way to tell.

    The subprocess exits 0 and prints one JSON object, or it does not and the failure is
    classified by its kind: a missing module is BLOCKED, anything else is reported.
    """
    result = runner.run(
        [sys.executable, "-c", _CANTOOLS_PROGRAM, str(dbc_path), frame],
        cwd=None,
        timeout_seconds=INSPECTION_TIMEOUT_SECONDS,
    )
    if result.exit_code is None:
        if getattr(result, "timed_out", False):
            raise InspectionUnavailable("CANTOOLS_TIMEOUT")
        raise InspectionUnavailable("CANTOOLS_UNAVAILABLE", "the decoder did not run")
    if result.exit_code != 0:
        stderr = (result.stderr or "").strip()
        if "ModuleNotFoundError" in stderr or "No module named" in stderr:
            raise InspectionUnavailable(
                "CANTOOLS_UNAVAILABLE", "cantools is not importable on this host"
            )
        raise InspectionUnavailable("CANTOOLS_FAILED", stderr[:200])

    try:
        decoded = json.loads((result.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise InspectionUnavailable("CANTOOLS_OUTPUT_UNREADABLE") from exc
    if not decoded.get("values"):
        raise InspectionUnavailable(
            "CANTOOLS_DECODED_NOTHING",
            "the DBC declares no signal for this frame; nothing would be compared",
        )
    return decoded


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


def run_binary(
    binary: str | Path, *, launcher: Sequence[str] = (), argv: Sequence[str] = ()
) -> Mapping[str, Any]:
    """§A.5. Execute the built binary and record what it printed and exited with.

    `launcher` is the emulator the task declares. An AArch64 binary MUST NOT be executed
    directly on the benchmark host: it would either fail with `Exec format error` or, on
    a host that happens to have binfmt registered, run through an emulator nobody
    declared and whose version is therefore not in the environment record.
    """
    completed = _run([*launcher, str(binary), *argv])
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
