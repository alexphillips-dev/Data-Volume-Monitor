#!/usr/bin/env python3
"""Run the same explicit checks locally and in GitHub Actions."""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
_channel_spec = importlib.util.spec_from_file_location('dvm_release_channel', Path(__file__).with_name('release_channel.py'))
_release = importlib.util.module_from_spec(_channel_spec)
_channel_spec.loader.exec_module(_release)


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def check_tracked(root):
    excluded = run(["git", "ls-files", "-ci", "--exclude-standard", "-z"],
                   cwd=root, capture_output=True).stdout
    if excluded:
        raise ValueError("Ignored local files are tracked: " + excluded.decode().replace("\0", ", "))
    paths = run(["git", "ls-files", "-z"], cwd=root, capture_output=True).stdout.decode().split("\0")
    for path in filter(None, paths):
        parts = Path(path).parts
        if any(part in {"AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "GEMINI.md", "__pycache__"}
               for part in parts):
            raise ValueError(f"Local instruction/cache file is tracked: {path}")


def check_backend_package(root, path, data):
    match = re.fullmatch(r'vnstat-([0-9]+\.[0-9]+)-x86_64-[0-9]+_dvm\.txz', path.name)
    if not match:
        raise ValueError('Unsupported backend package identity')
    version = match[1]
    for suffix, digest in [('md5', hashlib.md5(data).hexdigest()), ('sha256', hashlib.sha256(data).hexdigest())]:
        if Path(str(path) + '.' + suffix).read_text().strip() != f'{digest}  {path.name}':
            raise ValueError(f'Invalid backend {suffix} sidecar')
    metadata = json.loads((root / f'packages/vnstat-{version}-build.json').read_text())
    if metadata.get('package') != path.name or metadata.get('version') != version or metadata.get('sha256') != hashlib.sha256(data).hexdigest():
        raise ValueError('Invalid backend package provenance')
    source = root / f'packages/sources/vnstat-{version}.tar.gz'
    if hashlib.sha256(source.read_bytes()).hexdigest() != metadata.get('source_sha256'):
        raise ValueError('Invalid backend source provenance')
    binaries = {'usr/bin/vnstat': 'vnstat', 'usr/bin/vnstati': 'vnstati', 'usr/sbin/vnstatd': 'vnstatd'}
    docs = {f'usr/doc/vnstat-{version}/{name}': f'vnstat-{version}/{name}'
            for name in ['COPYING', 'CHANGES', 'README', 'INSTALL', 'UPGRADE', 'FAQ']}
    docs.update({f'usr/man/man{name[-1]}/{name}': f'vnstat-{version}/man/{name}'
                 for name in ['vnstat.1', 'vnstati.1', 'vnstatd.8', 'vnstat.conf.5']})
    required = set(binaries) | set(docs) | {'install/slack-desc'}
    with tarfile.open(path) as archive, tarfile.open(source) as upstream:
        entries = archive.getmembers()
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)) or set(names) != required:
            raise ValueError('Invalid backend package inventory')
        for entry in entries:
            allowed = entry.name in binaries or entry.name == 'install/slack-desc' or entry.name.startswith((f'usr/doc/vnstat-{version}/', 'usr/man/man'))
            if not allowed or not entry.isfile() or '..' in entry.name.split('/') or entry.uid != 0 or entry.gid != 0 or entry.mtime != 0:
                raise ValueError(f'Invalid backend payload: {entry.name}')
            if entry.mode != (0o755 if entry.name in binaries else 0o644):
                raise ValueError(f'Invalid backend permissions: {entry.name}')
            if entry.name in docs and archive.extractfile(entry).read() != upstream.extractfile(docs[entry.name]).read():
                raise ValueError(f'Invalid backend source document: {entry.name}')
            if entry.name in binaries:
                record = metadata.get('binaries', {}).get(binaries[entry.name], {})
                if hashlib.sha256(archive.extractfile(entry).read()).hexdigest() != record.get('sha256'):
                    raise ValueError(f'Invalid backend executable provenance: {entry.name}')


def check_package(root, expected_channel=None):
    channel = _release.expected_channel(root, expected_channel)
    base = _release.channel_base(channel)
    text = (root / 'plugin/dvm.plg').read_text(encoding='utf-8')
    manifest = ET.fromstring(text)
    version = manifest.attrib.get("version", "")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version):
        raise ValueError("Invalid plugin version")
    if _release.manifest_channel(text) != channel:
        raise ValueError(f'Manifest channel does not match expected {channel} channel')
    plugin_archive = None
    for entry in manifest.findall("FILE"):
        url = entry.findtext("URL")
        if url is None:
            continue
        if not url.startswith(base):
            raise ValueError(f"Unexpected download URL: {url}")
        relative = url[len(base):]
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Download is not a repository file: {relative}")
        data = path.read_bytes()
        if hashlib.md5(data).hexdigest() != entry.findtext("MD5"):
            raise ValueError(f"Manifest checksum mismatch: {relative}")
        if relative.startswith('packages/vnstat-'):
            check_backend_package(root, path, data)
        if relative.startswith("archive/"):
            if plugin_archive is not None or not re.fullmatch(rf"dvm-{re.escape(version)}-x86_64-[0-9]+\.txz", path.name):
                raise ValueError("Plugin package identity does not match its version")
            plugin_archive = path
            for suffix, digest in (("md5", hashlib.md5(data).hexdigest()),
                                   ("sha256", hashlib.sha256(data).hexdigest())):
                sidecar = path.with_suffix(".txz." + suffix).read_text().strip()
                if sidecar != f"{digest}  {path.name}":
                    raise ValueError(f"Invalid {suffix} sidecar")
    if plugin_archive is None:
        raise ValueError("Manifest has no plugin archive")
    source = root / "source"
    try:
        metadata = json.loads((source / _release.RELEASE_METADATA_REL).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError('Missing or invalid installed release metadata') from error
    if not isinstance(metadata, dict) or type(metadata.get('schema')) is not int or metadata != _release.release_metadata(channel, version):
        raise ValueError('Installed release metadata differs from the manifest channel or version')
    expected = {}
    def entries(directory):
        for entry in sorted(directory.iterdir()):
            yield entry
            if entry.is_dir() and not entry.is_symlink():
                yield from entries(entry)

    for path in entries(source):
        if path.is_symlink():
            raise ValueError(f"Source symlink is unsupported: {path}")
        if path.is_file():
            data = path.read_bytes()
            if b"\0" not in data and path.suffix != ".png":
                data = data.replace(b"\r\n", b"\n")
            expected[path.relative_to(source).as_posix()] = data
    if (root / ".git").exists():
        candidates = b"\0".join(("source/" + name).encode() for name in expected) + b"\0"
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"],
                                 cwd=root, input=candidates, capture_output=True)
        if ignored.returncode not in (0, 1):
            raise ValueError("Unable to verify package source against ignore rules")
        if ignored.stdout:
            raise ValueError("Ignored local files must not be packaged: " + ignored.stdout.decode().replace("\0", ", "))
    with tarfile.open(plugin_archive) as archive:
        members = archive.getmembers()
        names = [entry.name for entry in members]
        if any(name.startswith("/") or ".." in name.split("/") for name in names):
            raise ValueError("Archive contains an unsafe path")
        if len(names) != len(set(names)) or any(not (entry.isfile() or entry.isdir()) for entry in members):
            raise ValueError("Archive contains duplicate or unsupported entries")
        files = {entry.name: entry for entry in members if entry.isfile()}
        if set(files) != set(expected):
            raise ValueError("Archive file inventory differs from source")
        for name, data in expected.items():
            member = files[name]
            if archive.extractfile(member).read() != data:
                raise ValueError(f"Archive differs from source: {name}")
            mode = 0o755 if data.startswith(b"#!/") else 0o644
            if member.mode != mode or member.uid != 0 or member.gid != 0:
                raise ValueError(f"Incorrect package permissions: {name}")
    icon = root / "plugin/dvm.png"
    if icon.read_bytes() != (source / "usr/local/emhttp/plugins/dvm/images/dvm.png").read_bytes():
        raise ValueError("Repository and installed icons differ")
    # Rebuild in a copy, so validation never modifies the checked-out package.
    import tempfile
    import runpy
    with tempfile.TemporaryDirectory(prefix="dvm-repro-check-") as directory:
        fixture = Path(directory)
        shutil.copytree(source, fixture / "source")
        (fixture / "plugin").mkdir()
        shutil.copyfile(root / "plugin/dvm.plg", fixture / "plugin/dvm.plg")
        namespace = runpy.run_path(str(root / "scripts/build_package.py"))
        build = namespace["main"]
        build.__globals__.update(ROOT=fixture, SOURCE=fixture / "source", MANIFEST=fixture / "plugin/dvm.plg")
        build()
        if (fixture / "archive" / plugin_archive.name).read_bytes() != plugin_archive.read_bytes():
            raise ValueError("Published package does not reproduce from source")


def php_binary():
    value = os.environ.get("DVM_PHP_BIN")
    return value or ("/usr/bin/php8.3" if sys.platform == "linux" else "php")


def node_command(*arguments):
    executable = os.environ.get("DVM_NODE_BIN") or shutil.which("node") or shutil.which("node.exe")
    if not executable:
        raise ValueError("Node.js is required")
    args = list(map(str, arguments))
    # WSL can use Windows Node for local UI fixtures; hosted CI uses native Node.
    if sys.platform == "linux" and executable.lower().endswith(".exe"):
        args = [run(["wslpath", "-w", value], capture_output=True, text=True).stdout.strip()
                if Path(value).is_file() else value for value in args]
    return [executable, *args]


def check_syntax(root):
    for path in sorted((root / "source").rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if path.suffix in {".php", ".page"} or data.startswith(b"#!/usr/bin/php"):
            run([php_binary(), "-d", "short_open_tag=1", "-l", str(path)])
        if data.startswith(b"#!/bin/bash"):
            normalized = data.replace(b"\r\n", b"\n")
            run(["bash", "-n"], input=normalized)
            run(["shellcheck", "--severity=warning", "--exclude=SC1090", "--shell=bash", "-"], input=normalized)
        if path.suffix == ".js":
            run(node_command("--check", path))
    manifest = ET.parse(root / "plugin/dvm.plg").getroot()
    for inline in manifest.findall("./FILE/INLINE"):
        run(["bash", "-n"], input=inline.text.encode())


def check_tests(root):
    if sys.platform != "linux" or os.geteuid() == 0:
        raise ValueError("The complete suite needs unprivileged Linux for real permissions, symlinks and locks")
    run([php_binary(), "-r", "if (!class_exists('SimpleXMLElement')) exit(1);"])
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise ValueError(f"Python regressions failed or skipped ({len(result.skipped)} skipped)")
    for path in sorted((root / "tests").glob("*.php")):
        run([php_binary(), str(path)])
    for path in sorted((root / "tests").glob("*.mjs")):
        run(node_command(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", nargs="+", choices=["all", "tracked", "package", "syntax", "tests"], default=["all"])
    parser.add_argument('--channel', choices=['dev', 'main'], help='Expected channel; required for detached or non-channel checkouts')
    options = parser.parse_args()
    selected = ["tracked", "syntax", "tests", "package"] if "all" in options.checks else options.checks
    checks = {"tracked": check_tracked, "syntax": check_syntax, "tests": check_tests, "package": check_package}
    for name in selected:
        print(f"Checking {name}...", flush=True)
        if name == 'package':
            check_package(ROOT, options.channel)
        else:
            checks[name](ROOT)
        print(f"PASS: {name}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, ET.ParseError, tarfile.TarError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
