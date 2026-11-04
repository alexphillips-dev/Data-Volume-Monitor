#!/usr/bin/env python3
"""Build the Data Volume Monitor Slackware package from the current source."""

import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
MANIFEST = ROOT / "plugin/dvm.plg"
REQUIRED_SOURCE_FILES = (
    "install/doinst.sh", "install/slack-desc", "etc/rc.d/rc.vnstat",
    "usr/sbin/dvm-notify", "usr/local/emhttp/plugins/dvm/DVMsettings.page",
    "usr/local/emhttp/plugins/dvm/include/dvm_config.php",
    "usr/local/emhttp/plugins/dvm/include/dvm_release.php",
    "usr/local/emhttp/plugins/dvm/release.json",
)


def source_entries(directory):
    # Path.rglob can silently skip unreadable directories. A package must fail
    # if any source directory cannot be enumerated rather than omit its files.
    # WindowsPath ordering ignores case; use the literal filename on every OS
    # so a Windows build has the same archive order as Linux CI.
    for entry in sorted(directory.iterdir(), key=lambda path: path.name):
        if entry.is_symlink():
            raise ValueError(f"Symlinks are not supported in package source: {entry}")
        yield entry
        if entry.is_dir():
            yield from source_entries(entry)


def main():
    manifest = MANIFEST.read_text(encoding="utf-8")
    names = re.findall(r'<!ENTITY plgNAME\s+"([^"]+)">', manifest)
    checksums = re.findall(r'<!ENTITY plgMD5\s+"[a-f0-9]{32}">', manifest)
    if len(names) != 1 or len(checksums) != 1:
        raise ValueError("Expected exactly one package name and checksum in the manifest")
    try:
        ET.fromstring(manifest)
    except ET.ParseError as error:
        raise ValueError("Invalid plugin manifest") from error
    package = names[0]
    if not re.fullmatch(r"dvm-[0-9.]+-x86_64-[0-9]+", package):
        raise ValueError("Unexpected package name")
    if not SOURCE.is_dir() or SOURCE.is_symlink():
        raise ValueError("Package source directory is missing or is a symlink")
    missing = [name for name in REQUIRED_SOURCE_FILES if not (SOURCE / name).is_file()]
    if missing:
        raise ValueError(f"Package source is incomplete: {', '.join(missing)}")
    archive = ROOT / "archive" / f"{package}.txz"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz", format=tarfile.USTAR_FORMAT) as output:
        for path in source_entries(SOURCE):
            name = path.relative_to(SOURCE).as_posix()
            entry = tarfile.TarInfo(name)
            entry.uid = entry.gid = 0
            entry.uname = entry.gname = "root"
            entry.mtime = 0
            if path.is_dir():
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o755
                output.addfile(entry)
            elif path.is_file():
                data = path.read_bytes()
                if b"\0" not in data and path.suffix != ".png":
                    data = data.replace(b"\r\n", b"\n")
                entry.mode = 0o755 if data.startswith(b"#!/") else 0o644
                entry.size = len(data)
                output.addfile(entry, io.BytesIO(data))
            else:
                raise ValueError(f"Unsupported source entry: {path}")
    data = buffer.getvalue()
    md5 = hashlib.md5(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()
    manifest, count = re.subn(
        r'<!ENTITY plgMD5\s+"[a-f0-9]{32}">',
        f'<!ENTITY plgMD5    "{md5}">', manifest
    )
    if count != 1:
        raise ValueError("Expected exactly one package checksum in the manifest")
    outputs = {
        archive: data,
        archive.with_suffix(".txz.md5"): f"{md5}  {archive.name}\n".encode(),
        archive.with_suffix(".txz.sha256"): f"{sha256}  {archive.name}\n".encode(),
        MANIFEST: manifest.encode("utf-8"),
    }
    publish_outputs(outputs)
    print(f"Built {archive.relative_to(ROOT)}")
    print(f"SHA256 {sha256}")


def publish_outputs(outputs):
    """Stage all outputs, then replace; roll back handled publication failures.

    Each rename is atomic on the repository filesystem. Multiple files cannot
    be committed atomically, so publish the manifest last and restore prior
    files if a replacement fails. This is not a power-loss transaction.
    """
    staging = Path(tempfile.mkdtemp(prefix=".dvm-build-", dir=ROOT))
    cleanup = True
    try:
        backups = {}
        prepared = {}
        for index, (destination, data) in enumerate(outputs.items()):
            candidate = staging / f"new-{index}"
            candidate.write_bytes(data)
            candidate.chmod(0o644)
            prepared[destination] = candidate
            if destination.exists():
                backup = staging / f"old-{index}"
                backup.write_bytes(destination.read_bytes())
                backup.chmod(destination.stat().st_mode & 0o777)
                backups[destination] = backup
            else:
                backups[destination] = None
        replaced = []
        try:
            for destination, candidate in prepared.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(candidate, destination)
                replaced.append(destination)
        except OSError:
            failures = []
            for destination in reversed(replaced):
                backup = backups[destination]
                try:
                    if backup is None:
                        destination.unlink()
                    else:
                        os.replace(backup, destination)
                except OSError as error:
                    failures.append(str(error))
            if failures:
                cleanup = False
                raise RuntimeError(f"Build rollback failed; recovery files retained in {staging}: {failures}")
            raise
    finally:
        if cleanup:
            shutil.rmtree(staging)


if __name__ == "__main__":
    main()
