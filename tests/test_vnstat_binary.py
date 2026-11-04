"""Linux integration tests against the exact bundled vnStat executables.

Only a temporary database is used. --initdb exits immediately; no daemon is
started and no live database or workload is modified.
"""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PHP = Path("/usr/bin/php8.3")


def active_package():
    manifest = ET.parse(ROOT / 'plugin/dvm.plg').getroot()
    return ROOT / 'packages' / next(entry.findtext('URL').rsplit('/', 1)[1]
        for entry in manifest.findall('FILE') if '/packages/vnstat-' in (entry.findtext('URL') or ''))


@unittest.skipUnless(sys.platform == "linux" and PHP.is_file(), "Requires Linux and native /usr/bin/php8.3")
class NativeVnstatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dvm-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "db").mkdir()
        with tarfile.open(active_package()) as archive:
            for name, directory in (("vnstat", "bin"), ("vnstatd", "sbin"), ("vnstati", "bin")):
                binary = self.root / name
                binary.write_bytes(archive.extractfile(f"usr/{directory}/{name}").read())
                binary.chmod(0o755)
        self.config = self.root / "vnstat.conf"
        self.write_config(0)
        self.command("vnstatd", "--noadd", "--initdb", check=True)
        self.command("vnstat", "--add", "-i", "lo", check=True)
        self.db = self.root / "db/vnstat.db"
        with sqlite3.connect(self.db) as db:
            for table in ("hour", "day", "month", "year"):
                db.execute(f"INSERT INTO {table}(interface,date,rx,tx) VALUES(1,datetime('now'),0,0)")
        helper = ROOT / "source/usr/local/emhttp/plugins/dvm/include/dvm_threshold.php"
        self.runner = self.root / "evaluate.php"
        self.runner.write_text("<?php\nrequire " + json.dumps(str(helper)) + ";\n" + r'''
$runner = function ($command) use ($argv) {
    $command = str_replace('vnstat --config /etc/vnstat/vnstat.conf',
        escapeshellarg($argv[1]).' --config '.escapeshellarg($argv[2]), $command);
    exec($command, $lines, $status);
    return [implode("\n", $lines), $status];
};
echo dvm_threshold_evaluate($argv[3], $argv[4], $argv[5], $argv[6], $argv[7], $runner);
''')

    def write_config(self, unit_mode):
        self.config.write_text(f'DatabaseDir "{self.root / "db"}"\nPidFile "{self.root / "pid"}"\nUseLogging 0\nUnitMode {unit_mode}\n')

    def command(self, executable, *args, check=False):
        return subprocess.run([str(self.root / executable), "--config", str(self.config), *args],
                              text=True, capture_output=True, check=check, timeout=10)

    def evaluate(self, period="h", mode="rx", limit="1", unit="KB", iface="lo"):
        result = subprocess.run([str(PHP), str(self.runner), str(self.root / "vnstat"), str(self.config),
                                 iface, period, limit, unit, mode], text=True, capture_output=True, check=True, timeout=10)
        return result.stdout

    def set_usage(self, value):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE interface SET rxtotal=?,txtotal=?", (value, value))
            for table in ("hour", "day", "month", "year"):
                db.execute(f"UPDATE {table} SET rx=?,tx=?", (value, value))

    def test_all_packaged_executables_are_version_214(self):
        for name in ('vnstat', 'vnstatd', 'vnstati'):
            result = self.command(name, '--version', check=True)
            self.assertRegex(result.stdout, r'\b2\.14\b')

    def test_reserved_alias_characters_produce_valid_json_and_xml(self):
        alias = '<traffic>&"quoted"\\name'
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE interface SET alias=?', (alias,))
        data = json.loads(self.command('vnstat', '--json', '-i', 'lo', check=True).stdout)
        self.assertEqual(data['interfaces'][0]['alias'], alias)
        xml = ET.fromstring(self.command('vnstat', '--xml', '-i', 'lo', check=True).stdout)
        self.assertEqual(xml.findtext('interface/alias'), alias)

    def test_all_plugin_image_modes_generate_png_files(self):
        self.set_usage(1000)
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO fiveminute(interface,date,rx,tx) VALUES(1,datetime('now'),1000,1000)")
        for mode in ('s', '5', 'h', 'd', 'm', 'y'):
            with self.subTest(mode=mode):
                output = self.root / (mode + '.png')
                self.command('vnstati', '-' + mode, '-c', '1', '-o', str(output), '-i', 'lo', check=True)
                self.assertEqual(output.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_real_backend_through_all_php_report_modes(self):
        self.set_usage(1000)
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO fiveminute(interface,date,rx,tx) VALUES(1,datetime('now'),1000,1000)")
        images = self.root / 'images'
        images.mkdir()
        result = subprocess.run([str(PHP), str(ROOT / 'tests/fixtures/native_reports.php'),
                                 str(self.root), str(self.config), str(images)],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stderr, '')
        results = json.loads(result.stdout)
        for format, modes in results.items():
            for mode, record in modes.items():
                with self.subTest(format=format, mode=mode):
                    self.assertTrue(record['available'])
                    self.assertTrue(record['response'])
                    self.assertNotIn('dvm-threshold-error', record['response'])
                    if mode != 'report':
                        self.assertIn('red-text', record['response'])
                    if mode == 'dashboard':
                        self.assertEqual(len(record['response'].split(';')), 10)
        self.assertEqual(len(list(images.glob('*.png'))), 6)
        self.assertTrue(all(path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for path in images.iterdir()))

    def test_212_database_history_survives_upgrade(self):
        old = self.root / 'old'
        old.mkdir()
        with tarfile.open(ROOT / 'packages/vnstat-2.12-x86_64-1_slack14.2.txz') as archive:
            for name, directory in [('vnstat', 'bin'), ('vnstatd', 'sbin')]:
                path = old / name
                path.write_bytes(archive.extractfile(f'usr/{directory}/{name}').read())
                path.chmod(0o755)
        old_db = old / 'db'
        old_db.mkdir()
        config = old / 'vnstat.conf'
        config.write_text(f'DatabaseDir "{old_db}"\nPidFile "{old}/pid"\nUseLogging 0\n')
        for name, args in [('vnstatd', ['--noadd', '--initdb']), ('vnstat', ['--add', '-i', 'lo'])]:
            subprocess.run([str(old / name), '--config', str(config), *args], check=True, capture_output=True)
        with sqlite3.connect(old_db / 'vnstat.db') as db:
            for period in ('fiveminute', 'hour', 'day', 'month', 'year'):
                db.execute(f"INSERT INTO {period}(interface,date,rx,tx) VALUES(1,'2026-01-01 00:00:00',1234,5678)")
            db.execute('UPDATE interface SET rxtotal=1234,txtotal=5678,alias=?', ('Saved history',))
            before = [line for line in db.iterdump() if "'vnstatversion'" not in line]
        for name, args in [('vnstatd', ['--noadd', '--initdb']), ('vnstat', ['--json', '-i', 'lo'])]:
            result = subprocess.run([str(self.root / name), '--config', str(config), *args], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data['interfaces'][0]['traffic']['total'], {'rx':1234, 'tx':5678})
        with sqlite3.connect(old_db / 'vnstat.db') as db:
            self.assertEqual([line for line in db.iterdump() if "'vnstatversion'" not in line], before)
            self.assertEqual(db.execute("SELECT value FROM info WHERE name='vnstatversion'").fetchone()[0], '2.14')
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_shipped_configuration_preserves_dvm_defaults(self):
        shipped = ROOT / 'source/usr/local/emhttp/plugins/dvm/vnstat/vnstat.conf'
        result = subprocess.run([str(self.root / 'vnstat'), '--config', str(shipped), '--showconfig'],
                                text=True, capture_output=True, check=True)
        for key, value in [('UpdateInterval', 20), ('PollInterval', 5), ('SaveInterval', 1),
                           ('OfflineSaveInterval', 10), ('RescanDatabaseOnSave', 1), ('AlwaysAddNewInterfaces', 1)]:
            self.assertRegex(result.stdout, rf'(?m)^;?{key}\s+{value}\s*$')

    def test_native_units_periods_directions_and_boundaries(self):
        legacy = self.root / 'vnstat-212'
        with tarfile.open(ROOT / 'packages/vnstat-2.12-x86_64-1_slack14.2.txz') as archive:
            legacy.write_bytes(archive.extractfile('usr/bin/vnstat').read())
        legacy.chmod(0o755)
        for unit_mode, factor in ((0, 1024), (1, 1000), (2, 1000)):
            self.write_config(unit_mode)
            for usage in (factor - 1, factor, factor + 1):
                self.set_usage(usage)
                for period in ("h", "d", "m", "y"):
                    for mode in ("rx", "tx"):
                        with self.subTest(unit_mode=unit_mode, usage=usage, period=period, mode=mode):
                            old = self.command("vnstat", "--alert", "0", "3", period, mode, "1", "KB", "-i", "lo")
                            self.assertIn(old.returncode, (0, 1), old.stderr)
                            self.assertEqual(old.stdout, "", "Valid native threshold unexpectedly emitted an error")
                            expected = "exceeded" if old.returncode else "normal"
                            self.assertEqual(self.evaluate(period, mode), expected)
                            prior = subprocess.run([str(legacy), '--config', str(self.config), '--alert', '0', '3',
                                                    period, mode, '1', 'KB', '-i', 'lo'], text=True, capture_output=True)
                            self.assertEqual(prior.returncode, old.returncode, prior.stderr + prior.stdout)

    def test_missing_period_data_is_error_even_with_zero_backend_status(self):
        with sqlite3.connect(self.db) as db:
            db.execute("DELETE FROM hour")
        raw = self.command("vnstat", "--json", "--alert", "1", "0", "h", "rx", "1", "KB", "-i", "lo")
        self.assertEqual(raw.returncode, 0)
        self.assertIn("Error:", raw.stdout)
        self.assertEqual(self.evaluate(), "error")

    def test_invalid_missing_and_overflow_inputs_are_errors(self):
        self.set_usage(2000)
        self.assertEqual(self.evaluate(limit="-2"), "error")
        self.assertEqual(self.evaluate(iface="missing"), "error")
        self.assertEqual(self.evaluate(limit="18446744073709551615", unit="GB"), "error")

    def test_disabled_and_leading_zero_inputs(self):
        self.set_usage(2000)
        self.assertEqual(self.evaluate(limit="-1"), "disabled")
        self.assertEqual(self.evaluate(limit="0001"), "exceeded")

    def test_effective_paths_from_native_showconfig(self):
        helper = ROOT / "source/usr/local/emhttp/plugins/dvm/include/dvm_config_guard.php"
        runner = self.root / "paths.php"
        runner.write_text("<?php\nrequire " + json.dumps(str(helper)) + ";\n" + r'''
$reader = function ($path) use ($argv) {
    exec(escapeshellarg($argv[1]).' --config '.escapeshellarg($path).' --showconfig 2>/dev/null', $lines, $status);
    if ($status !== 0) throw new RuntimeException('Native configuration query failed');
    return implode("\n", $lines);
};
echo json_encode(dvm_config_effective_paths($argv[2], $reader));
''')
        cases = [
            ('UseLogging 0\n', '/var/lib/vnstat/', '/var/run/vnstat/vnstat.pid'),
            (f'DatabaseDir "{self.root}/custom data"\nPidFile "{self.root}/custom pid"\nUseLogging 0\n',
             f'{self.root}/custom data/', f'{self.root}/custom pid'),
        ]
        for contents, database, pid in cases:
            with self.subTest(database=database):
                self.config.write_text(contents)
                result = subprocess.run([str(PHP), str(runner), str(self.root / "vnstat"), str(self.config)],
                                        text=True, capture_output=True, check=True, timeout=10)
                self.assertEqual(json.loads(result.stdout), {'DatabaseDir': database, 'PidFile': pid})


if __name__ == "__main__":
    unittest.main()
