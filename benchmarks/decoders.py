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
import re
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


#: A program version as a compiled program carries it: a product name, a space, and
#: `v<major>.<minor>[.<patch>]`. MEASURED against the pinned lab's statically linked
#: AArch64 binary, where it matches the injected `-DFW_VERSION_STR` literal and nothing
#: else in 635 KB of glibc, DWARF and source-path strings.
_PROGRAM_VERSION_TOKEN = re.compile(rb"\b[A-Za-z][A-Za-z0-9_.+-]*[ \t]+v\d+(?:\.\d+)+\b")

#: Every ELF file starts with these four bytes. A file that does not is not a program.
_ELF_MAGIC = b"\x7fELF"


def _elf_program_versions(rootfs: Path) -> set[str]:
    """Every version string carried by an ELF executable under `rootfs`."""
    versions: set[str] = set()
    for path in sorted(rootfs.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:  # pragma: no cover - an unreadable file is not a program
            continue
        if not data.startswith(_ELF_MAGIC):
            continue
        for match in _PROGRAM_VERSION_TOKEN.finditer(data):
            versions.add(match.group(0).decode("ascii", "replace"))
    return versions


def _program_version(rootfs: Path) -> str:
    """§A.4. The PROGRAM version, read from the program IN THE EXTRACTED IMAGE.

    ```text
    NOT /etc/banner   a boot banner is not a program version. On the pinned v1 image the
                      banner reads "SYNTHETIC ECU boot banner - revision 1" while the
                      program reports "SYN-ECU v1.0". An oracle that answered with the
                      banner was answering a different question, and it made every
                      firmware run UNKNOWN against its own tracked truth.
    NOT config.ini    the pinned v1 config has no `version` key at all, so a config-first
                      read has nothing to read and MUST NOT invent one.
    NOT truth         the observation is what the image contains, never what the corpus
                      says it should contain.
    ```

    The version lives where the build put it: `build_fw.sh` compiles the program with
    `-DFW_VERSION_STR`, so the string is in the executable and nowhere else.

    Failure is `InspectionUnavailable`, never a value. An image whose programs carry no
    version has not been observed, and an empty string would be a value nobody measured;
    two programs that disagree are not a fact to round to one of them. §8.2 makes both
    BLOCKED — "we could not look" is not "we looked and it was wrong", and it is
    certainly not a pass.
    """
    versions = _elf_program_versions(rootfs)
    if not versions:
        raise InspectionUnavailable(
            "PROGRAM_VERSION_ABSENT",
            f"no ELF executable under {rootfs} carries a '<name> v<major>.<minor>' "
            "version string. The program version is not in the image; the boot banner "
            "and the config are not substitutes for it",
        )
    if len(versions) > 1:
        raise InspectionUnavailable(
            "PROGRAM_VERSION_AMBIGUOUS",
            f"the image's executables carry more than one program version: "
            f"{sorted(versions)}. An ambiguous version is never guessed",
        )
    return versions.pop()


def inspect_firmware(image: str | Path, *, extract_to: str | Path) -> Mapping[str, Any]:
    """§A.4. Filesystem, compression, program version and admin_password, from the IMAGE.

    `binwalk` identifies the filesystem and its compression; `unsquashfs` extracts it so
    the program and the config can be read out of the rootfs. The expected values are
    never read from a fixture and the image digest is never asserted — `build_fw.sh`
    calls `mksquashfs` without a reproducible-time flag, so the digest is not stable and
    is recorded as a measured fact only.

    Every value comes from the image: two from `binwalk`'s report of the image, one from
    a program the image contains, and one from the config file the image contains. None
    of them comes from a name, a fixture, or the truth the answer is judged against.
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

    return {
        "filesystem": filesystem,
        "compression": compression or "unknown",
        # From the executable in the extracted rootfs. The image's boot banner and its
        # config are NOT sources for it, and there is no fallback to either: a fallback
        # is what turned a boot banner into a program version.
        "version": _program_version(extract_to),
        "admin_password": values.get("admin_password", ""),
    }
