"""Storage path tests operate on temporary databases, never a live vnStat DB."""
import os
import hashlib
import io
import tarfile
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "bash"


class StoragePathTests(unittest.TestCase):
    def functions(self):
        source = (ROOT / "source/etc/rc.d/rc.vnstat").read_text()
        return source[source.index('backup_db() {'):source.index('write_config() {')]

    def test_backup_uses_configured_database(self):
        source = (ROOT / "source/etc/rc.d/rc.vnstat").read_text()
        functions = source[source.index('backup_db() {'):source.index('write_config() {')]
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom database'
            backup = root / 'flash backup'
            custom.mkdir(); backup.mkdir()
            (custom / 'vnstat.db').write_bytes(b'custom traffic history')
            script = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\nsleep() {{ :; }}\n' + functions + '\nbackup_db\n'
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((backup / 'vnstat.db').is_file(), 'Custom database was not backed up')
            self.assertEqual((backup / 'vnstat.db').read_bytes(), b'custom traffic history')

    def test_failed_metadata_write_preserves_previous_backup_pair(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom database'
            backup = root / 'flash backup'
            custom.mkdir(); backup.mkdir()
            (custom / 'vnstat.db').write_bytes(b'new custom traffic')
            (backup / 'vnstat.db').write_bytes(b'old backup traffic')
            marker = '/old/database/vnstat.db\n' + hashlib.sha256(b'old backup traffic').hexdigest() + '\n'
            (backup / 'vnstat.db.path').write_text(marker, newline='\n')
            script = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\nprintf() {{ return 1; }}\n' + self.functions() + '\nbackup_db\n'
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((backup / 'vnstat.db').read_bytes(), b'old backup traffic')
            self.assertEqual((backup / 'vnstat.db.path').read_text(), marker)

    def test_interrupted_backup_publication_cannot_restore_wrong_data(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
                root = Path(folder)
                custom = root / 'custom database'; backup = root / 'flash backup'
                custom.mkdir(); backup.mkdir()
                (custom / 'vnstat.db').write_bytes(b'new custom traffic')
                (backup / 'vnstat.db').write_bytes(b'old backup traffic')
                if not legacy:
                    (backup / 'vnstat.db.path').write_text('/old/database/vnstat.db\n' + hashlib.sha256(b'old backup traffic').hexdigest() + '\n', newline='\n')
                setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\n'
                fail_move = 'mv() { if [ "${@: -1}" = "$PLGPATH/vnstat.db" ]; then return 1; fi; command mv "$@"; }\n'
                result = subprocess.run([BASH], input=setup + fail_move + self.functions() + '\nbackup_db\n', text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((backup / 'vnstat.db').read_bytes(), b'old backup traffic')
                (custom / 'vnstat.db').unlink()
                result = subprocess.run([BASH], input=setup + self.functions() + '\nrestore_db\n', text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((custom / 'vnstat.db').exists())

    def test_failed_new_publication_can_restore_previous_matching_generation(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom database'; backup = root / 'flash backup'
            custom.mkdir(); backup.mkdir()
            (custom / 'vnstat.db').write_bytes(b'new traffic')
            (backup / 'vnstat.db').write_bytes(b'previous valid traffic')
            marker = (custom / 'vnstat.db').as_posix() + '\n' + hashlib.sha256(b'previous valid traffic').hexdigest() + '\n'
            (backup / 'vnstat.db.path').write_text(marker, newline='\n')
            setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\nchown() {{ :; }}\n'
            fail_move = 'mv() { if [ "${@: -1}" = "$PLGPATH/vnstat.db" ]; then return 1; fi; command mv "$@"; }\n'
            result = subprocess.run([BASH], input=setup + fail_move + self.functions() + '\nbackup_db\n', text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            (custom / 'vnstat.db').unlink()
            result = subprocess.run([BASH], input=setup + self.functions() + '\nrestore_db\n', text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((custom / 'vnstat.db').read_bytes(), b'previous valid traffic')

    def test_invalid_current_cannot_replace_valid_previous_generation(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom database'; backup = root / 'flash backup'
            custom.mkdir(); backup.mkdir()
            data = b'last known good traffic'
            marker = ((custom / 'vnstat.db').as_posix() + '\n' + hashlib.sha256(data).hexdigest() + '\n').encode()
            archive = backup / 'vnstat.previous.tar'
            with tarfile.open(archive, 'w') as output:
                for name, payload in [('vnstat.db', data), ('vnstat.db.path', marker)]:
                    item = tarfile.TarInfo(name); item.size = len(payload)
                    output.addfile(item, io.BytesIO(payload))
            before = archive.read_bytes()
            (backup / 'vnstat.db').write_bytes(b'corrupt current')
            (backup / 'vnstat.db.path').write_bytes(marker)
            (custom / 'vnstat.db').write_bytes(b'new valid traffic')
            setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\nchown() {{ :; }}\n'
            result = subprocess.run([BASH], input=setup + self.functions() + '\nbackup_db\n', text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(archive.read_bytes(), before)
            (custom / 'vnstat.db').unlink()
            (backup / 'vnstat.db').write_bytes(b'new current became corrupt')
            result = subprocess.run([BASH], input=setup + self.functions() + '\nrestore_db\n', text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((custom / 'vnstat.db').read_bytes(), data)

    def test_failed_previous_rotation_keeps_both_existing_generations(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom'; backup = root / 'backup'
            custom.mkdir(); backup.mkdir()
            (custom / 'vnstat.db').write_bytes(b'new traffic')
            (backup / 'vnstat.db').write_bytes(b'current backup')
            marker = (custom / 'vnstat.db').as_posix() + '\n' + hashlib.sha256(b'current backup').hexdigest() + '\n'
            (backup / 'vnstat.db.path').write_text(marker, newline='\n')
            (backup / 'vnstat.previous.tar').write_bytes(b'untouched previous archive')
            setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\ntar() {{ return 1; }}\n'
            result = subprocess.run([BASH], input=setup + self.functions() + '\nbackup_db\n', text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((backup / 'vnstat.db').read_bytes(), b'current backup')
            self.assertEqual((backup / 'vnstat.db.path').read_text(), marker)
            self.assertEqual((backup / 'vnstat.previous.tar').read_bytes(), b'untouched previous archive')
            self.assertEqual(sorted(p.name for p in backup.iterdir()), ['vnstat.db', 'vnstat.db.path', 'vnstat.previous.tar'])

    def test_previous_archive_requires_matching_path_and_checksum(self):
        for wrong_path, wrong_hash in [(True, False), (False, True)]:
            with self.subTest(wrong_path=wrong_path, wrong_hash=wrong_hash), tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
                root = Path(folder); custom = root / 'custom'; backup = root / 'backup'
                custom.mkdir(); backup.mkdir()
                data = b'previous traffic'
                marker = ('/different/vnstat.db' if wrong_path else (custom / 'vnstat.db').as_posix()) + '\n'
                marker += ('0' * 64 if wrong_hash else hashlib.sha256(data).hexdigest()) + '\n'
                with tarfile.open(backup / 'vnstat.previous.tar', 'w') as output:
                    for name, payload in [('vnstat.db', data), ('vnstat.db.path', marker.encode())]:
                        item = tarfile.TarInfo(name); item.size = len(payload); output.addfile(item, io.BytesIO(payload))
                setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\n'
                result = subprocess.run([BASH], input=setup + self.functions() + '\nrestore_db\n', text=True, capture_output=True)
                self.assertEqual(result.returncode, 1 if wrong_hash else 0, result.stderr)
                self.assertFalse((custom / 'vnstat.db').exists())
                self.assertEqual([p.name for p in backup.iterdir()], ['vnstat.previous.tar'])

    def test_failed_restore_does_not_leave_partial_runtime_database(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder); custom = root / 'custom'; backup = root / 'backup'
            custom.mkdir(); backup.mkdir()
            (backup / 'vnstat.db').write_bytes(b'backup traffic')
            marker = (custom / 'vnstat.db').as_posix() + '\n' + hashlib.sha256(b'backup traffic').hexdigest() + '\n'
            (backup / 'vnstat.db.path').write_text(marker, newline='\n')
            setup = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\n'
            failure = 'cp() { printf partial > "${@: -1}"; return 1; }\n'
            result = subprocess.run([BASH], input=setup + failure + self.functions() + '\nrestore_db\n', text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(custom.iterdir()), [])

    def test_restore_requires_matching_location_and_keeps_existing_data(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            custom = root / 'custom database'
            backup = root / 'flash backup'
            custom.mkdir(); backup.mkdir()
            (backup / 'vnstat.db').write_bytes(b'backup traffic')
            digest = hashlib.sha256(b'backup traffic').hexdigest()
            (backup / 'vnstat.db.path').write_text('/different/location/vnstat.db\n' + digest + '\n', newline='\n')
            script = f'BACKUPDB=enable\nDATABASEDIR="{custom.as_posix()}"\nDATABASEFILE="$DATABASEDIR/vnstat.db"\nPLGPATH="{backup.as_posix()}"\nchown() {{ :; }}\n' + self.functions() + '\nrestore_db\n'
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((custom / 'vnstat.db').exists())
            (backup / 'vnstat.db.path').write_text((custom / 'vnstat.db').as_posix() + '\n' + digest + '\n', newline='\n')
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((custom / 'vnstat.db').read_bytes(), b'backup traffic')
            (custom / 'vnstat.db').write_bytes(b'newer runtime traffic')
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((custom / 'vnstat.db').read_bytes(), b'newer runtime traffic')

    def test_remove_database_does_not_remove_custom_directory_or_other_files(self):
        with tempfile.TemporaryDirectory(prefix="dvm-storage-test-") as folder:
            root = Path(folder)
            for name in ['vnstat.db', 'vnstat.db-wal', 'vnstat.db-shm', 'vnstat.db-journal', 'keep.txt']:
                (root / name).write_text('fixture')
            script = f'DATABASEFILE="{root.as_posix()}/vnstat.db"\nload_paths() {{ :; }}\n' + self.functions() + '\nremove_database\n'
            result = subprocess.run([BASH], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['keep.txt'])

    def test_reset_config_preserves_custom_database_location(self):
        source = (ROOT / 'source/usr/local/emhttp/plugins/dvm/scripts/resetconf').read_text()
        with tempfile.TemporaryDirectory(prefix="dvm-reset-test-") as folder:
            root = Path(folder)
            for name in ['fixture_boot/vnstat', 'fixture_source/vnstat', 'fixture_runtime']:
                (root / name).mkdir(parents=True)
            (root / 'fixture_source/default.cfg').write_text('SERVICE="disable"\n')
            (root / 'fixture_source/vnstat/vnstat.conf').write_text(';DatabaseDir "/var/lib/vnstat"\n')
            for name in ['dvm-custom-alarms.sh', 'dvm-user-actions.sh']:
                (root / 'fixture_source/vnstat' / name).write_text('#!/bin/bash\n')
            (root / 'fixture_runtime/vnstat.db').write_bytes(b'preserved history')
            (root / 'fixture_boot/vnstat/vnstat.db').write_bytes(b'stale mirrored history')
            (root / 'fixture_boot/vnstat/custom-helper.sh').write_text('# custom persisted helper\n')
            service = root / 'service'
            service.write_text('#!/bin/bash\nif [ "$1" = database_path ]; then echo /etc/vnstat; fi\nexit 0\n', newline='\n')
            service.chmod(0o755)
            source = source.replace('/etc/rc.d/rc.vnstat', './service').replace('/boot/config/plugins/dvm', 'fixture_boot').replace('/usr/local/emhttp/plugins/dvm', 'fixture_source').replace('/etc/vnstat', 'fixture_runtime').replace('/tmp/dvm*notified', 'fixture_notified*')
            result = subprocess.run([BASH], input='chown() { :; }\n' + source, text=True, capture_output=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('DatabaseDir "/etc/vnstat"', (root / 'fixture_runtime/vnstat.conf').read_text())
            self.assertEqual((root / 'fixture_runtime/vnstat.db').read_bytes(), b'preserved history')
            self.assertIn('custom persisted helper', (root / 'fixture_runtime/custom-helper.sh').read_text())

    def test_reset_all_keeps_selected_location_and_does_not_reselect_old_history(self):
        source = (ROOT / 'source/usr/local/emhttp/plugins/dvm/scripts/resetall').read_text()
        with tempfile.TemporaryDirectory(prefix="dvm-reset-test-") as folder:
            root = Path(folder)
            for name in ['fixture_boot/vnstat', 'fixture_source/vnstat', 'fixture_runtime', 'active_database', 'default_database']:
                (root / name).mkdir(parents=True)
            (root / 'fixture_source/default.cfg').write_text('SERVICE="disable"\n')
            (root / 'fixture_source/vnstat/vnstat.conf').write_text(';DatabaseDir "/var/lib/vnstat"\n')
            for name in ['dvm-custom-alarms.sh', 'dvm-user-actions.sh']:
                (root / 'fixture_source/vnstat' / name).write_text('#!/bin/bash\n')
            (root / 'active_database/vnstat.db').write_text('current history')
            (root / 'default_database/vnstat.db').write_text('old default history')
            (root / 'fixture_boot/vnstat.previous.tar').write_bytes(b'previous archive to clear')
            service = root / 'service'
            service.write_text('#!/bin/bash\ncase "$1" in database_path) echo /mnt/cache/active_database;; remove_database) rm -f active_database/vnstat.db;; esac\nexit 0\n', newline='\n')
            service.chmod(0o755)
            source = source.replace('/etc/rc.d/rc.vnstat', './service').replace('/boot/config/plugins/dvm', 'fixture_boot').replace('/usr/local/emhttp/plugins/dvm', 'fixture_source').replace('/etc/vnstat', 'fixture_runtime').replace('/tmp/dvm*notified', 'fixture_notified*')
            result = subprocess.run([BASH], input='chown() { :; }\nphp() { printf "%s\\n" "$*" > outcome-cleanup; }\n' + source, text=True, capture_output=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'outcome-cleanup').read_text().strip(), 'fixture_source/include/dvm_outcome_store.php clear')
            self.assertIn('DatabaseDir "/mnt/cache/active_database"', (root / 'fixture_runtime/vnstat.conf').read_text())
            self.assertFalse((root / 'active_database/vnstat.db').exists())
            self.assertEqual((root / 'default_database/vnstat.db').read_text(), 'old default history')
            self.assertFalse((root / 'fixture_boot/vnstat.previous.tar').exists())

    def test_install_restores_extra_configs_but_not_a_stale_database(self):
        source = (ROOT / 'source/install/doinst.sh').read_text()
        with tempfile.TemporaryDirectory(prefix="dvm-install-test-") as folder:
            root = Path(folder)
            for name in ['fixture_boot/vnstat', 'fixture_source/vnstat', 'fixture_runtime']:
                (root / name).mkdir(parents=True)
            (root / 'fixture_source/default.cfg').write_text('SERVICE="disable"\n')
            for name in ['vnstat.conf', 'dvm-custom-alarms.sh', 'dvm-user-actions.sh']:
                (root / 'fixture_source/vnstat' / name).write_text('# default\n')
            (root / 'fixture_runtime/vnstat.db').write_bytes(b'latest runtime traffic')
            (root / 'fixture_boot/vnstat/vnstat.db').write_bytes(b'stale mirrored traffic')
            (root / 'fixture_boot/vnstat/custom-helper.sh').write_text('# custom helper\n')
            (root / 'fixture_boot/vnstat/extra.conf').write_text('# extra config\n')
            source = source.replace('/boot/config/plugins/dvm', 'fixture_boot').replace('/usr/local/emhttp/plugins/dvm', 'fixture_source').replace('/etc/vnstat', 'fixture_runtime').replace('/etc/cron.daily/dvm-poller', 'fixture_poller')
            result = subprocess.run([BASH], input='chmod() { :; }\nchown() { :; }\n' + source, text=True, capture_output=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'fixture_runtime/vnstat.db').read_bytes(), b'latest runtime traffic')
            self.assertIn('custom helper', (root / 'fixture_runtime/custom-helper.sh').read_text())
            self.assertIn('extra config', (root / 'fixture_runtime/extra.conf').read_text())


if __name__ == "__main__":
    unittest.main()
