"""Lifecycle regression checks using only temporary executables and shell mocks."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RC = ROOT / "source/etc/rc.d/rc.vnstat"
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\bin\bash.exe"


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dvm-lifecycle-test-")
        self.addCleanup(self.temp.cleanup)
        self.daemon = Path(self.temp.name) / "daemon"
        self.daemon.write_text("#!/bin/bash\nexit 23\n", encoding="utf-8", newline="\n")
        self.daemon.chmod(0o755)
        self.hook = Path(self.temp.name) / 'remove-hook'
        self.hook.write_text('#!/bin/bash\nexit 0\n', newline='\n')
        self.hook.chmod(0o755)
        self.mocks = """
rm() { echo UNEXPECTED_DELETE; return 0; }
sleep() { return 0; }
cp() { return 0; }
mkdir() { return 0; }
chmod() { return 0; }
chown() { return 0; }
killall() { return 1; }
removepkg() { echo UNEXPECTED_REMOVE; return 0; }
update_cron() { return 0; }
logger() { cat >/dev/null; }
php() { return 0; }
"""

    def run_shell(self, script):
        return subprocess.run([BASH], input=script, text=True, capture_output=True)

    def functions(self):
        text = RC.read_text()
        return text[text.index("check_daemon() {"):text.index('case "$1" in')].replace(
            "/usr/sbin/vnstatd", '"' + self.daemon.as_posix() + '"'
        )

    def replace_service(self, text):
        return text.replace("/etc/rc.d/rc.vnstat", '"' + self.daemon.as_posix() + '"').replace(
            '/usr/local/emhttp/plugins/dvm/scripts/remove_shutdown_hook', '"' + self.hook.as_posix() + '"')

    def test_daemon_failure_is_nonzero(self):
        result = self.run_shell(self.mocks + '\nCONFIGFILE=/dev/null\nPIDFILE=/missing-dvm-test-pid\nDAEMON=vnstatd\npgrep() { return 1; }\n' + self.functions() + "\nvnstat_start\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_failed_stop_is_nonzero(self):
        result = self.run_shell(self.mocks + "\nDAEMON=vnstatd\npgrep() { return 0; }\n" + self.functions() + "\nvnstat_stop\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_process_query_failure_cannot_be_treated_as_stopped(self):
        for action in ('vnstat_stop', 'vnstat_status'):
            with self.subTest(action=action):
                result = self.run_shell(self.mocks + "\nDAEMON=vnstatd\npgrep() { return 2; }\n" + self.functions() + '\n' + action + '\n')
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('UNEXPECTED_DELETE', result.stdout)

    def test_stopped_status_is_nonzero(self):
        result = self.run_shell(self.mocks + "\nPIDFILE=/missing-dvm-test-pid\nDAEMON=vnstatd\npgrep() { return 1; }\n" + self.functions() + "\nvnstat_status\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_successful_start_and_stop(self):
        self.daemon.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8", newline="\n")
        script = self.mocks + '\nCONFIGFILE=/dev/null\nDAEMON=vnstatd\ncalls=0\npgrep() { calls=$((calls+1)); [ "$calls" -gt 1 ]; }\n'
        result = self.run_shell(script + self.functions() + "\nvnstat_start\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.mocks + '\nDAEMON=vnstatd\nrunning=1\npgrep() { [ "$running" -eq 1 ]; }\nkillall() { running=0; return 0; }\n'
        result = self.run_shell(script + self.functions() + "\nvnstat_stop\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_restart_does_not_start_after_failed_stop(self):
        script = self.mocks + '\nDAEMON=vnstatd\npgrep() { return 0; }\n'
        script += self.functions() + '\nwrite_config() { echo UNEXPECTED_WRITE; }\nvnstat_start() { echo UNEXPECTED_START; }\nvnstat_restart\n'
        result = self.run_shell(script)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('UNEXPECTED_WRITE', result.stdout)
        self.assertNotIn('UNEXPECTED_START', result.stdout)

    def test_wrappers_preserve_failure(self):
        for name in ("start", "stop", "restart", "write_config"):
            with self.subTest(name=name):
                text = (ROOT / "source/usr/local/emhttp/plugins/dvm/scripts" / name).read_text()
                result = self.run_shell(self.mocks + self.replace_service(text))
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_resets_abort_before_delete_when_stop_fails(self):
        for name in ("resetconf", "resetall"):
            with self.subTest(name=name):
                text = (ROOT / "source/usr/local/emhttp/plugins/dvm/scripts" / name).read_text()
                result = self.run_shell(self.mocks + self.replace_service(text))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("UNEXPECTED_DELETE", result.stdout)

    def test_installer_aborts_on_service_failures(self):
        manifest = ET.parse(ROOT / "plugin/dvm.plg").getroot()
        for index, inline in enumerate(manifest.findall("./FILE/INLINE")):
            with self.subTest(index=index):
                result = self.run_shell(self.mocks + '\nSERVICE=enable\n' + self.replace_service(inline.text))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("UNEXPECTED_DELETE", result.stdout)
                self.assertNotIn("UNEXPECTED_REMOVE", result.stdout)

    def test_uninstall_aborts_if_package_removal_fails(self):
        self.daemon.write_text("#!/bin/bash\nif [ \"$1\" = database_path ]; then echo /fixture/database; fi\nexit 0\n", encoding="utf-8", newline="\n")
        inline = ET.parse(ROOT / 'plugin/dvm.plg').getroot().find('./FILE[@Method="remove"]/INLINE').text
        result = self.run_shell(self.mocks + '\nremovepkg() { echo PACKAGE_REMOVE_ATTEMPT; return 23; }\n' + self.replace_service(inline))
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('PACKAGE_REMOVE_ATTEMPT', result.stdout)
        self.assertNotIn('UNEXPECTED_DELETE', result.stdout)

    def test_uninstall_aborts_before_package_removal_if_hook_cleanup_fails(self):
        self.daemon.write_text('#!/bin/bash\nif [ "$1" = database_path ]; then echo /fixture/database; fi\nexit 0\n', newline='\n')
        self.hook.write_text('#!/bin/bash\necho HOOK_REMOVE_ATTEMPT\nexit 23\n', newline='\n')
        inline = ET.parse(ROOT / 'plugin/dvm.plg').getroot().find('./FILE[@Method="remove"]/INLINE').text
        result = self.run_shell(self.mocks + self.replace_service(inline))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('HOOK_REMOVE_ATTEMPT', result.stdout)
        self.assertNotIn('UNEXPECTED_REMOVE', result.stdout)
        self.assertNotIn('UNEXPECTED_DELETE', result.stdout)

    def test_persistence_setting_installs_or_removes_hook_and_propagates_failure(self):
        source = RC.read_text()
        start = source.index('  if [ "$BACKUPDB" == "enable" ]; then', source.index('write_config() {'))
        block = source[start:source.index('  if [ "$GOODNOTIFY"', start)]
        scripts = Path(self.temp.name) / 'scripts'
        scripts.mkdir()
        for name in ('install_shutdown_hook', 'remove_shutdown_hook'):
            file = scripts / name
            file.write_text('#!/bin/bash\necho ' + name + '\nexit "${HOOK_STATUS:-0}"\n', newline='\n')
            file.chmod(0o755)
        for enabled, expected in [('enable', 'install_shutdown_hook'), ('disable', 'remove_shutdown_hook')]:
            for status in (0, 23):
                with self.subTest(enabled=enabled, status=status):
                    prefix = f'DOCROOT="{Path(self.temp.name).as_posix()}"\nBACKUPDB={enabled}\nexport HOOK_STATUS={status}\nrestore_db() {{ echo RESTORE; }}\n'
                    result = self.run_shell(prefix + 'apply_setting() {\n' + block + '\n}\napply_setting\n')
                    self.assertEqual(result.returncode == 0, status == 0, result.stderr)
                    self.assertIn(expected, result.stdout)
                    self.assertEqual('RESTORE' in result.stdout, enabled == 'enable' and status == 0)

    def test_outcome_cleanup_failure_aborts_reset_and_uninstall_before_deletion(self):
        self.daemon.write_text('#!/bin/bash\ncase "$1" in database_path) echo /fixture/database;; remove_database) echo UNEXPECTED_DB_DELETE;; esac\nexit 0\n', newline='\n')
        reset = (ROOT / 'source/usr/local/emhttp/plugins/dvm/scripts/resetall').read_text().split('echo "Deleting existing')[0]
        uninstall = ET.parse(ROOT / 'plugin/dvm.plg').getroot().find('./FILE[@Method="remove"]/INLINE').text
        for operation, script in [('reset', reset), ('uninstall', uninstall)]:
            with self.subTest(operation=operation):
                result = self.run_shell(self.mocks + '\nphp() { echo "OUTCOME_CLEAR $*"; return 31; }\n' + self.replace_service(script))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('dvm_outcome_store.php clear', result.stdout)
                self.assertNotIn('UNEXPECTED_DELETE', result.stdout)
                self.assertNotIn('UNEXPECTED_DB_DELETE', result.stdout)
                self.assertNotIn('UNEXPECTED_REMOVE', result.stdout)


if __name__ == "__main__":
    unittest.main()
