"""Check the actual dependency's source signature and Linux runtime contract."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BackendPackageTests(unittest.TestCase):
    def test_signed_corresponding_source_and_package_provenance(self):
        metadata = json.loads((ROOT / 'packages/vnstat-2.14-build.json').read_text())
        source = ROOT / 'packages/sources/vnstat-2.14.tar.gz'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), metadata['source_sha256'])
        archive = ROOT / 'packages' / metadata['package']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), metadata['sha256'])
        with tempfile.TemporaryDirectory(prefix='dvm-source-signature-') as directory:
            Path(directory).chmod(0o700)
            subprocess.run(['gpg', '--homedir', directory, '--batch', '--import', str(source.parent / 'vnstat-author.asc')],
                           check=True, capture_output=True)
            result = subprocess.run(['gpg', '--homedir', directory, '--batch', '--status-fd=1', '--verify',
                                     str(source) + '.asc', str(source)], text=True, capture_output=True, check=True)
            self.assertIn('VALIDSIG 23EF1DD76E65248FB055201ADAFE84E63D140114 ', result.stdout)
        with tarfile.open(source) as upstream, tarfile.open(archive) as packaged:
            for name in ('COPYING', 'CHANGES', 'UPGRADE', 'README', 'INSTALL', 'FAQ'):
                self.assertEqual(upstream.extractfile('vnstat-2.14/' + name).read(),
                                 packaged.extractfile('usr/doc/vnstat-2.14/' + name).read())

    def test_executable_abi_has_no_modern_glibc_or_local_paths(self):
        metadata = json.loads((ROOT / 'packages/vnstat-2.14-build.json').read_text())
        with tempfile.TemporaryDirectory(prefix='dvm-dependency-abi-') as directory, \
                tarfile.open(ROOT / 'packages' / metadata['package']) as archive:
            for name, folder in [('vnstat', 'bin'), ('vnstatd', 'sbin'), ('vnstati', 'bin')]:
                binary = Path(directory) / name
                binary.write_bytes(archive.extractfile(f'usr/{folder}/{name}').read())
                self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), metadata['binaries'][name]['sha256'])
                version = subprocess.check_output(['readelf', '--version-info', str(binary)], text=True)
                glibc = [tuple(map(int, value.split('.'))) for value in re.findall(r'GLIBC_([0-9.]+)', version)]
                self.assertLessEqual(max(glibc), (2, 17))
                dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
                self.assertNotRegex(dynamic, r'\((?:RPATH|RUNPATH)\)')
                needed = sorted(re.findall(r'Shared library: \[([^]]+)\]', dynamic))
                expected = ['libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libsqlite3.so.0']
                if name == 'vnstati': expected.append('libgd.so.3')
                self.assertEqual(needed, sorted(expected))
                header = subprocess.check_output(['readelf', '-h', str(binary)], text=True)
                self.assertIn('Advanced Micro Devices X86-64', header)
                self.assertIn(b'/lib64/ld-linux-x86-64.so.2', binary.read_bytes())


if __name__ == '__main__':
    unittest.main()
