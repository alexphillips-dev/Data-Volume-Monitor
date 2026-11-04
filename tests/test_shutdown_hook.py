"""Shutdown-hook checks use temporary host-script fixtures only."""
import base64
import os
import stat
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "/bin/bash"
PHP = 'php' if os.name == 'nt' else '/usr/bin/php8.3'
HELPER = ROOT / 'source/usr/local/emhttp/plugins/dvm/include/dvm_shutdown_hook.php'


class ShutdownHookTests(unittest.TestCase):
    def install(self, path, fail_publish=False, remove=False):
        if not HELPER.exists():
            # Replay the exact old integration until the replacement exists.
            source = (ROOT / 'source/etc/rc.d/rc.vnstat').read_text()
            start = source.index('    if [ "$( grep -ic ')
            fragment = source[start:source.index('    restore_db', start)]
            fragment = fragment.replace('/etc/rc.d/rc.local_shutdown', '"' + path.as_posix() + '"')
            return subprocess.run([BASH], input=fragment, text=True, capture_output=True)
        encoded = [base64.b64encode(str(p).encode()).decode() for p in (HELPER, path, BASH)]
        script = '''require base64_decode('%s');
$validator = function ($candidate) {
    $p = proc_open([base64_decode('%s'), '-n', $candidate], [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']], $pipes);
    if (!is_resource($p)) return false;
    fclose($pipes[0]); stream_get_contents($pipes[1]); fclose($pipes[1]); stream_get_contents($pipes[2]); fclose($pipes[2]);
    return proc_close($p) === 0;
};
try { %s(base64_decode('%s'), $validator, %s); } catch (Throwable $e) { fwrite(STDERR, $e->getMessage()); exit(1); }
''' % (encoded[0], encoded[2], 'dvm_remove_shutdown_hook' if remove else 'dvm_install_shutdown_hook', encoded[1], 'function () { return false; }' if fail_publish else 'null')
        return subprocess.run([PHP, '-r', script], text=True, capture_output=True)

    def test_removal_is_idempotent_and_preserves_foreign_hooks(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            original = '#!/bin/bash\necho host\n'
            path.write_text(original, newline='\n')
            self.assertEqual(self.install(path).returncode, 0)
            foreign = '/etc/rc.d/rc.vnstat status > /custom/log\n'
            with path.open('a') as stream:
                stream.write(foreign)
            for _ in range(2):
                result = self.install(path, remove=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(path.read_text(), original + foreign)

    def test_removal_handles_legacy_missing_and_failed_publication(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            self.assertEqual(self.install(path, remove=True).returncode, 0)
            self.assertFalse(path.exists())
            original = '#!/bin/sh\n[ -x /etc/rc.d/rc.vnstat ] && /etc/rc.d/rc.vnstat backup_db | logger\necho host\n'
            path.write_text(original, newline='\n')
            result = self.install(path, remove=True, fail_publish=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), original)
            result = self.install(path, remove=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text(), '#!/bin/sh\necho host\n')

    def test_missing_old_comment_anchor_still_installs_once(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            path.write_text('#!/bin/bash\n# Revised host layout\necho shutdown\n', newline='\n')
            result = self.install(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text().count('/etc/rc.d/rc.vnstat backup_db'), 1)
            first = path.read_bytes()
            result = self.install(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_bytes(), first)

    def test_foreign_comment_is_preserved_and_not_mistaken_for_a_hook(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            foreign = '# See /etc/rc.d/rc.vnstat for status\necho foreign\n'
            path.write_text('#!/bin/sh\n' + foreign, newline='\n')
            result = self.install(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(foreign, path.read_text())
            self.assertEqual(path.read_text().count('/etc/rc.d/rc.vnstat backup_db'), 1)

    def test_missing_host_script_reports_failure_without_creating_it(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'missing_shutdown'
            result = self.install(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(path.exists())

    def test_legacy_hook_is_migrated_and_host_contents_and_modes_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            legacy = '[ -x /etc/rc.d/rc.vnstat ] && /etc/rc.d/rc.vnstat backup_db | logger\n'
            suffix = '# Get time-out setting\necho "host shutdown"\n'
            path.write_text('#!/usr/bin/env bash\n' + legacy + suffix, newline='\n')
            path.chmod(0o750)
            mode = stat.S_IMODE(path.stat().st_mode)
            result = self.install(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(legacy, path.read_text())
            self.assertTrue(path.read_text().endswith(suffix))
            self.assertEqual(path.read_text().count('/etc/rc.d/rc.vnstat backup_db'), 1)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)

    def test_unknown_hook_unsupported_script_and_invalid_syntax_are_not_rewritten(self):
        originals = [
            '#!/bin/bash\n/etc/rc.d/rc.vnstat backup_db > /custom/log\n',
            '#!/usr/bin/python\nprint("shutdown")\n',
            '#!/bin/sh\nif then\n',
        ]
        for original in originals:
            with self.subTest(original=original), tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
                path = Path(folder) / 'rc.local_shutdown'
                path.write_text(original, newline='\n')
                result = self.install(path)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(path.read_text(), original)

    def test_failed_publication_preserves_original_host_file(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            original = '#!/bin/bash\necho original\n'
            path.write_text(original, newline='\n')
            result = self.install(path, fail_publish=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), original)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['rc.local_shutdown'])

    def test_early_host_exit_follows_hook_and_backup_failure_does_not_stop_shutdown(self):
        with tempfile.TemporaryDirectory(prefix='dvm-hook-test-') as folder:
            path = Path(folder) / 'rc.local_shutdown'
            path.write_text('#!/bin/bash\necho HOST-RAN\nexit 0\n', newline='\n')
            result = self.install(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            service = Path(folder) / 'fake-service'
            service.write_text('#!/bin/bash\nexit 23\n', newline='\n')
            service.chmod(0o755)
            script = path.read_text().replace('/etc/rc.d/rc.vnstat', '"' + service.as_posix() + '"')
            result = subprocess.run([BASH, '-e'], input='logger() { echo "$*"; return 1; }\n' + script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('backup failed (exit 23)', result.stdout)
            self.assertIn('HOST-RAN', result.stdout)


if __name__ == '__main__':
    unittest.main()
