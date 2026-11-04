"""Exercise CI's package and tracked-file guards with isolated repositories."""
import contextlib
import io
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import json

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = runpy.run_path(str(ROOT / "scripts/validate_repository.py"))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dvm-validation-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("source", "plugin", "packages", "scripts"):
            shutil.copytree(ROOT / name, self.root / name)
        manifest = ET.parse(self.root / 'plugin/dvm.plg').getroot()
        self.channel = 'main' if '/main/plugin/dvm.plg' in manifest.attrib['pluginURL'] else 'dev'
        self.release_file = self.root / 'source/usr/local/emhttp/plugins/dvm/release.json'
        self.release_file.write_text(json.dumps({'schema': 1, 'channel': self.channel,
            'version': manifest.attrib['version'], 'plugin_url': manifest.attrib['pluginURL']}) + '\n')
        build = runpy.run_path(str(self.root / "scripts/build_package.py"))["main"]
        with contextlib.redirect_stdout(io.StringIO()):
            build()

    def package(self):
        with contextlib.redirect_stdout(io.StringIO()):
            VALIDATE["check_package"](self.root, self.channel)

    def test_expected_main_rejects_dev_manifest(self):
        manifest = self.root / 'plugin/dvm.plg'
        manifest.write_text(manifest.read_text().replace('/main"', '/dev"'))
        with self.assertRaisesRegex(ValueError, 'channel'):
            VALIDATE['check_package'](self.root, 'main')

    def test_stable_candidate_passes_with_explicit_channel(self):
        manifest = self.root / 'plugin/dvm.plg'
        manifest.write_text(manifest.read_text().replace('/dev"', '/main"'))
        release = json.loads(self.release_file.read_text())
        release.update(channel='main', plugin_url='https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/main/plugin/dvm.plg')
        self.release_file.write_text(json.dumps(release) + '\n')
        build = runpy.run_path(str(self.root / 'scripts/build_package.py'))['main']
        with contextlib.redirect_stdout(io.StringIO()):
            build()
            VALIDATE['check_package'](self.root, 'main')

    def test_main_checkout_cannot_silently_validate_dev_metadata(self):
        manifest = self.root / 'plugin/dvm.plg'
        manifest.write_text(manifest.read_text().replace('/main"', '/dev"'))
        subprocess.run(['git', 'init', '--quiet', '--initial-branch=main'], cwd=self.root, check=True)
        with self.assertRaisesRegex(ValueError, 'channel'):
            VALIDATE['check_package'](self.root)

    def test_mixed_download_channel_is_rejected(self):
        manifest = self.root / 'plugin/dvm.plg'
        text = manifest.read_text().replace('<URL>&pkgURL;/', '<URL>https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/' + ('dev' if self.channel == 'main' else 'main') + '/packages/')
        manifest.write_text(text)
        with self.assertRaisesRegex(ValueError, 'download URL'):
            self.package()

    def test_stale_release_metadata_is_rejected(self):
        release = json.loads(self.release_file.read_text())
        release['channel'] = 'main' if self.channel == 'dev' else 'dev'
        self.release_file.write_text(json.dumps(release))
        with self.assertRaisesRegex(ValueError, 'release metadata'):
            self.package()

    def test_release_metadata_schema_and_extra_fields_are_rejected(self):
        valid = json.loads(self.release_file.read_text())
        for invalid in [dict(valid, schema=True), dict(valid, schema='1'), dict(valid, extra='unknown')]:
            with self.subTest(metadata=invalid):
                self.release_file.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(ValueError, 'release metadata'):
                    self.package()

    def test_unknown_or_missing_release_metadata_is_rejected(self):
        self.release_file.write_text('not JSON')
        with self.assertRaisesRegex(ValueError, 'release metadata'):
            self.package()
        self.release_file.unlink()
        with self.assertRaisesRegex(ValueError, 'release metadata'):
            self.package()

    def test_matching_package_passes(self):
        self.package()

    def test_stale_packaged_source_is_rejected(self):
        with (self.root / "source/usr/sbin/dvm-notify").open("ab") as stream:
            stream.write(b"\n# modified after package build\n")
        with self.assertRaisesRegex(ValueError, "differs from source"):
            self.package()

    def test_dependency_corruption_is_rejected(self):
        manifest = ET.parse(self.root / 'plugin/dvm.plg').getroot()
        name = next(entry.findtext('URL').rsplit('/', 1)[1] for entry in manifest.findall('FILE')
                    if '/packages/' in (entry.findtext('URL') or ''))
        dependency = self.root / 'packages' / name
        dependency.write_bytes(b"invalid archive")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.package()

    def test_backend_checksum_sidecar_corruption_is_rejected(self):
        sidecar = self.root / 'packages/vnstat-2.14-x86_64-1_dvm.txz.sha256'
        sidecar.write_text('0' * 64 + '  wrong.txz\n')
        with self.assertRaisesRegex(ValueError, 'backend.*sidecar'):
            self.package()

    def test_backend_provenance_corruption_is_rejected(self):
        import json
        provenance = self.root / 'packages/vnstat-2.14-build.json'
        data = json.loads(provenance.read_text())
        data['source_sha256'] = '0' * 64
        provenance.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'backend.*source'):
            self.package()

    def test_backend_missing_license_is_rejected(self):
        import hashlib
        import json
        import tarfile
        archive = self.root / 'packages/vnstat-2.14-x86_64-1_dvm.txz'
        before = archive.read_bytes()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(before)) as original, \
                tarfile.open(fileobj=buffer, mode='w:xz', format=tarfile.USTAR_FORMAT) as replacement:
            for entry in original:
                if not entry.name.endswith('/COPYING'):
                    replacement.addfile(entry, original.extractfile(entry))
        data = buffer.getvalue()
        archive.write_bytes(data)
        for suffix, digest in [('md5', hashlib.md5(data).hexdigest()), ('sha256', hashlib.sha256(data).hexdigest())]:
            Path(str(archive) + '.' + suffix).write_text(f'{digest}  {archive.name}\n')
        provenance = self.root / 'packages/vnstat-2.14-build.json'
        metadata = json.loads(provenance.read_text())
        metadata['sha256'] = hashlib.sha256(data).hexdigest()
        provenance.write_text(json.dumps(metadata))
        manifest = self.root / 'plugin/dvm.plg'
        manifest.write_text(manifest.read_text().replace(hashlib.md5(before).hexdigest(), hashlib.md5(data).hexdigest()))
        with self.assertRaisesRegex(ValueError, 'backend.*inventory'):
            self.package()

    def test_checksum_sidecar_corruption_is_rejected(self):
        sidecar = next((self.root / "archive").glob("*.sha256"))
        sidecar.write_text("0" * 64 + "  wrong.txz\n")
        with self.assertRaisesRegex(ValueError, "sidecar"):
            self.package()

    def test_tracked_local_file_is_rejected_but_ignored_copy_is_allowed(self):
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text("AGENTS.md\n")
        (self.root / "AGENTS.md").write_text("local-only fixture\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=self.root, check=True)
        VALIDATE["check_tracked"](self.root)
        subprocess.run(["git", "add", "--force", "AGENTS.md"], cwd=self.root, check=True)
        with self.assertRaisesRegex(ValueError, "tracked"):
            VALIDATE["check_tracked"](self.root)

    def test_package_version_mismatch_is_rejected(self):
        manifest = self.root / "plugin/dvm.plg"
        text = manifest.read_text()
        import re
        text = re.sub(r'<!ENTITY version\s+"[^"]+">', '<!ENTITY version "9999.01.01">', text)
        manifest.write_text(text)
        with self.assertRaisesRegex(ValueError, "identity"):
            self.package()

    def test_ignored_local_source_cannot_leak_into_package(self):
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text(".env\n!.env.example\n")
        (self.root / "source/.env").write_text("fixture-local-data\n")
        (self.root / "source/.env.example").write_text("EXAMPLE=\n")
        build = runpy.run_path(str(self.root / "scripts/build_package.py"))["main"]
        with contextlib.redirect_stdout(io.StringIO()):
            build()
        with self.assertRaisesRegex(ValueError, "Ignored local files"):
            self.package()
        (self.root / "source/.env").unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            build()
        self.package()


if __name__ == "__main__":
    unittest.main()
