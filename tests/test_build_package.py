"""Package builds must preserve existing deliverables when a build fails."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class PackageBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dvm-build-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source/install").mkdir(parents=True)
        (self.root / "plugin").mkdir()
        (self.root / "archive").mkdir()
        (self.root / "source/install/doinst.sh").write_bytes(b"#!/bin/bash\r\nexit 0\r\n")
        self.manifest = self.root / "plugin/dvm.plg"
        self.manifest.write_bytes((ROOT / "plugin/dvm.plg").read_bytes())
        namespace = runpy.run_path(str(ROOT / "scripts/build_package.py"))
        for name in namespace.get("REQUIRED_SOURCE_FILES", ()):
            required = self.root / "source" / name
            required.parent.mkdir(parents=True, exist_ok=True)
            if not required.exists():
                required.write_text("fixture payload\n")
        self.build = namespace["main"]
        self.build.__globals__.update(ROOT=self.root, SOURCE=self.root / "source", MANIFEST=self.manifest)

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.build()

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for base in (self.root / "archive", self.root / "plugin")
                for p in base.rglob("*") if p.is_file()}

    def test_reproducible_valid_build_and_matching_checksum(self):
        self.run_build()
        before = self.snapshot()
        self.run_build()
        self.assertEqual(before, self.snapshot())
        archive = next((self.root / "archive").glob("*.txz"))
        manifest = ET.parse(self.manifest).getroot()
        package = [f for f in manifest.findall("FILE") if "/archive/" in (f.findtext("URL") or "")][0]
        self.assertEqual(hashlib.md5(archive.read_bytes()).hexdigest(), package.findtext("MD5"))

    def test_mixed_case_entries_have_platform_independent_order(self):
        import tarfile
        folder = self.root / "source/mixed-case"
        folder.mkdir()
        for name in ("default.cfg", "DVM.page", "LICENSE", "css"):
            (folder / name).write_text("fixture\n")
        self.run_build()
        with tarfile.open(next((self.root / "archive").glob("*.txz"))) as archive:
            names = [entry.name for entry in archive.getmembers()
                     if entry.name.startswith("mixed-case/")]
        self.assertEqual(names, sorted(names))

    def test_invalid_manifest_preserves_all_existing_outputs(self):
        self.run_build()
        self.manifest.write_text(self.manifest.read_text().replace("plgMD5", "invalidMD5"))
        before = self.snapshot()
        (self.root / "source/install/doinst.sh").write_text("#!/bin/bash\nexit 1\n")
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_source_read_failure_preserves_all_existing_outputs(self):
        self.run_build()
        before = self.snapshot()
        original_read = Path.read_bytes
        source_file = self.root / "source/install/doinst.sh"

        def failing_read(path):
            if path == source_file:
                raise OSError("simulated unreadable source")
            return original_read(path)

        with mock.patch.object(Path, "read_bytes", failing_read):
            with self.assertRaises(OSError):
                self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_publication_failure_rolls_back_existing_outputs(self):
        self.run_build()
        before = self.snapshot()
        (self.root / "source/install/doinst.sh").write_text("#!/bin/bash\nexit 1\n")
        original_replace = os.replace
        calls = 0

        def failing_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("simulated output replacement failure")
            return original_replace(source, destination)

        with mock.patch.object(os, "replace", failing_replace):
            with self.assertRaises(OSError):
                self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_invalid_xml_preserves_existing_outputs(self):
        self.run_build()
        self.manifest.write_text(self.manifest.read_text().replace("</PLUGIN>", "</BROKEN>"))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_failed_rollback_retains_recovery_copy(self):
        self.run_build()
        archive = next((self.root / "archive").glob("*.txz"))
        original_archive = archive.read_bytes()
        (self.root / "source/install/doinst.sh").write_text("#!/bin/bash\nexit 1\n")
        original_replace = os.replace
        calls = 0

        def failing_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls >= 2:
                raise OSError("simulated persistent filesystem failure")
            return original_replace(source, destination)

        with mock.patch.object(os, "replace", failing_replace):
            with self.assertRaisesRegex(RuntimeError, "recovery files retained"):
                self.run_build()
        recovery = list(self.root.glob(".dvm-build-*/old-0"))
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0].read_bytes(), original_archive)

    def test_missing_source_preserves_existing_outputs(self):
        self.run_build()
        before = self.snapshot()
        (self.root / "source").rename(self.root / "source-unavailable")
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_empty_source_preserves_existing_outputs(self):
        self.run_build()
        before = self.snapshot()
        (self.root / "source").rename(self.root / "source-unavailable")
        (self.root / "source").mkdir()
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_missing_required_payload_preserves_existing_outputs(self):
        self.run_build()
        before = self.snapshot()
        (self.root / "source/usr/sbin/dvm-notify").unlink()
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    @unittest.skipUnless(os.name == "posix" and os.geteuid() != 0, "Requires unprivileged POSIX permission checks")
    def test_unreadable_directory_preserves_existing_outputs(self):
        directory = self.root / "source/private"
        directory.mkdir()
        (directory / "payload.conf").write_text("must not silently disappear\n")
        self.run_build()
        before = self.snapshot()
        directory.chmod(0)
        try:
            with self.assertRaises(OSError):
                self.run_build()
            self.assertEqual(before, self.snapshot())
        finally:
            directory.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
