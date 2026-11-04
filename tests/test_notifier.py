"""Isolated notifier regressions: no real service, workload, or system path access."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\bin\bash.exe"
HELPER = ROOT / "source/usr/local/emhttp/plugins/dvm/include/dvm_threshold.php"


class Fixture:
    def __init__(self, overrides="", state="exceeded", query_status=0, slow=False, vm_failure=False, docker_status=0, notification_status=0):
        self.temp = tempfile.TemporaryDirectory(prefix="dvm-notifier-test-")
        self.root = Path(self.temp.name)
        for directory in ["sys", "tmp", "locks"]:
            (self.root / directory).mkdir()
        (self.root / "sys/eth0").touch()
        (self.root / "sys/eth1").touch()
        (self.root / "sys/vnet0").touch()
        self.record = self.root / "record"
        cfg = (ROOT / "source/usr/local/emhttp/plugins/dvm/default.cfg").read_text()
        (self.root / "config").write_text(cfg + '\nBADNOTIFY=enable\nBADACTIONS=enable\nRXLIMITH=1\nRXUNITH=B\n' + overrides, newline="\n")
        payload = {"interfaces": [{"name": "eth0", "alert": {"type": "hour", "limit": {"exceeded": state == "exceeded", "condition": "rx", "limit_bytes": 1, "used_bytes": 2 if state == "exceeded" else 0}}}]}
        if state == "malformed":
            payload = {"interfaces": []}
        (self.root / "query.json").write_text(json.dumps(payload))
        runner = "<?php\nrequire " + json.dumps(HELPER.as_posix()) + ";\n"
        runner += "$args = array_slice($argv, 1); $runner = function ($command) { return [file_get_contents(__DIR__.'/query.json'), " + str(query_status) + "]; };\n"
        runner += "$state = dvm_threshold_evaluate($args[0], $args[1], $args[2], $args[3], $args[4], $runner); echo $state; exit($state === 'error' ? 3 : 0);\n"
        (self.root / "runner.php").write_text(runner)
        script = (ROOT / "source/usr/sbin/dvm-notify").read_text()
        script = script.replace('/tmp/', self.root.as_posix() + '/tmp/')
        script = script.replace('/var/lock/', self.root.as_posix() + '/locks/')
        script = script.replace('/sys/class/net/', self.root.as_posix() + '/sys/')
        script = script.replace('/etc/vnstat/dvm.cfg', (self.root / "config").as_posix())
        script = script.replace('/etc/vnstat/dvm-user-actions.sh', (self.root / "absent").as_posix())
        script = script.replace('/usr/local/emhttp/plugins/dynamix/scripts/notify', 'notify_mock')
        script = script.replace('/usr/local/emhttp/plugins/dvm/include/dvm_threshold.php', (self.root / "runner.php").as_posix())
        outcome_helper = ROOT / 'source/usr/local/emhttp/plugins/dvm/include/dvm_outcome_store.php'
        if outcome_helper.exists():
            (self.root / 'outcome.php').write_text(outcome_helper.read_text()
                .replace('/var/run/dvm/outcomes', (self.root / 'outcomes').as_posix())
                .replace('/etc/vnstat/dvm.cfg', (self.root / 'config').as_posix())
                .replace('/etc/vnstat/dvm-user-actions.sh', (self.root / 'absent').as_posix()))
        script = script.replace('/usr/local/emhttp/plugins/dvm/include/dvm_outcome_store.php', (self.root / 'outcome.php').as_posix())
        prefix = f'RECORD="{self.record.as_posix()}"\n'
        if os.name != 'nt':
            prefix += 'php() { /usr/bin/php8.3 "$@"; }\n'
        prefix += 'pgrep() { return 0; }\nlogger() { cat >/dev/null; }\nhour_rx_reached() { return 0; }\nhour_rx_normal_again() { return 0; }\n'
        prefix += 'notify_mock() { printf "NOTIFY %s\\n" "$*" >> "$RECORD"; ' + f'return {notification_status}; }}\n'
        prefix += 'docker() { printf "DOCKER %s\\n" "$*" >> "$RECORD"; ' + ('sleep 2; ' if slow else '') + f'return {docker_status}; }}\n'
        listing = 'printf "Interface Type\\n-----------\\nvnet0 bridge\\n";'
        if vm_failure is True:
            listing = 'return 1;'
        elif vm_failure == 'empty':
            listing = 'printf "Interface Type\\n-----------\\n";'
        elif vm_failure == 'mixed':
            listing = 'printf "Interface Type\\n-----------\\nvnet0 bridge\\nmissing bridge\\n";'
        prefix += 'virsh() { if [ "$1" = domiflist ]; then ' + listing + ' else printf "VIRSH %s\\n" "$*" >> "$RECORD"; ' + ('return 1;' if vm_failure == 'link' else 'return 0;') + ' fi; }\n'
        prefix += 'vnstat() { if [[ "$*" == *--dbiflist* ]]; then echo "Interfaces in database: eth0 eth1"; return 0; fi; '
        if state == "malformed":
            prefix += 'echo "Valid parameters for --alert"; return 1; }\n'
        elif query_status:
            prefix += 'echo "backend unavailable" >&2; return 1; }\n'
        else:
            prefix += f'return {1 if state == "exceeded" else 0}; }}\n'
        self.script = prefix + script

    def run(self, *args):
        return subprocess.run([BASH, '-s', '--', *args], input=self.script.encode(), capture_output=True, timeout=30)

    def output(self):
        return self.record.read_text() if self.record.exists() else ""

    def payload_for(self, iface, period='hour', mode='rx'):
        path = self.root / 'query.json'
        payload = json.loads(path.read_text())
        payload['interfaces'][0]['name'] = iface
        payload['interfaces'][0]['alert']['type'] = period
        payload['interfaces'][0]['alert']['limit']['condition'] = mode
        path.write_text(json.dumps(payload))

    def outcomes(self):
        php = '/usr/bin/php8.3' if os.name != 'nt' else 'php'
        code = 'require ' + json.dumps((self.root / 'outcome.php').as_posix()) + '; echo json_encode(dvm_outcome_list());'
        return json.loads(subprocess.check_output([php, '-r', code]))

    def close(self):
        self.temp.cleanup()


class ThresholdTests(unittest.TestCase):
    def check_no_actions(self, **kwargs):
        fixture = Fixture(overrides="RXDOCKERHSTOP=test\n", **kwargs)
        try:
            fixture.run()
            self.assertNotIn("DOCKER", fixture.output())
            self.assertNotIn("NOTIFY", fixture.output())
            self.assertFalse((fixture.root / 'tmp/dvm_h_bad_rx_notified').exists())
        finally:
            fixture.close()

    def test_backend_error_preserves_unknown_state(self):
        self.check_no_actions(query_status=1)

    def test_malformed_result_does_not_trigger(self):
        self.check_no_actions(state="malformed")

    def test_valid_exceeded_and_repeat(self):
        fixture = Fixture(overrides="RXDOCKERHSTOP=test\n")
        try:
            fixture.run(); fixture.run()
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            fixture.close()

    def test_invalid_limit_does_not_trigger(self):
        fixture = Fixture(overrides="RXLIMITH=-2\nRXDOCKERHSTOP=test\n", state="malformed")
        try:
            fixture.run()
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_query_error_preserves_existing_marker(self):
        fixture = Fixture(overrides="GOODACTIONS=enable\nRXDOCKERHSTART=test\n", query_status=1)
        marker = fixture.root / 'tmp/dvm_h_bad_rx_notified'
        marker.touch()
        try:
            fixture.run()
            self.assertTrue(marker.exists())
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_normal_transition_runs_recovery(self):
        fixture = Fixture(overrides="GOODACTIONS=enable\nRXDOCKERHSTART=test\n", state="normal")
        marker = fixture.root / 'tmp/dvm_h_bad_rx_notified'
        marker.touch()
        try:
            fixture.run()
            self.assertFalse(marker.exists())
            self.assertIn('DOCKER start test', fixture.output())
        finally:
            fixture.close()

    def test_disabled_limit_does_not_trigger(self):
        fixture = Fixture(overrides="RXLIMITH=-1\nRXDOCKERHSTOP=test\n")
        try:
            fixture.run()
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_all_six_secondary_slots_use_shared_evaluator(self):
        for slot in range(1, 7):
            fixture = Fixture(overrides=f"RXLIMITH=-1\nCUSTOM{slot}INTERFACE=eth1\nCUSTOM{slot}LIMIT=1\nCUSTOM{slot}UNIT=B\nCUSTOM{slot}STOP=test{slot}\n")
            fixture.payload_for('eth1')
            try:
                fixture.run()
                self.assertIn(f'DOCKER stop test{slot}', fixture.output())
            finally:
                fixture.close()


class ConcurrencyTests(unittest.TestCase):
    def test_lock_failure_never_runs_actions(self):
        fixture = Fixture(overrides="RXDOCKERHSTOP=test\n")
        fixture.script = 'flock() { return 64; }\n' + fixture.script
        try:
            self.assertNotEqual(fixture.run().returncode, 0)
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_overlapping_runs_execute_once(self):
        fixture = Fixture(overrides="RXDOCKERHSTOP=test\n", slow=True)
        try:
            with ThreadPoolExecutor() as pool:
                futures = [pool.submit(fixture.run) for _ in range(2)]
                for future in futures:
                    future.result()
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
            (fixture.root / 'tmp/dvm_h_bad_rx_notified').unlink()
            fixture.run()
            self.assertEqual(fixture.output().count('DOCKER stop test'), 2)
        finally:
            fixture.close()


class VmTests(unittest.TestCase):
    def test_failed_query_never_reports_success(self):
        fixture = Fixture(overrides="RXVMHSTOP=missing\n", vm_failure=True)
        try:
            fixture.run()
            self.assertNotIn("disconnected with success", fixture.output())
            self.assertIn("disconnected with errors", fixture.output())
            self.assertNotIn("VIRSH", fixture.output())
        finally:
            fixture.close()

    def test_empty_failed_or_partly_missing_links_report_error(self):
        for failure in ['empty', 'link', 'mixed']:
            fixture = Fixture(overrides="RXVMHSTOP=test\n", vm_failure=failure)
            try:
                fixture.run()
                self.assertNotIn('disconnected with success', fixture.output())
                self.assertIn('disconnected with errors', fixture.output())
            finally:
                fixture.close()

    def test_secondary_and_recovery_paths(self):
        for secondary, recovery in [(False, True), (True, False), (True, True)]:
            overrides = 'GOODACTIONS=enable\n'
            if secondary:
                overrides += 'RXLIMITH=-1\nCUSTOM1INTERFACE=eth1\nCUSTOM1LIMIT=1\nCUSTOM1UNIT=B\n'
                overrides += 'CUSTOM1VM' + ('START' if recovery else 'STOP') + '=test\n'
            else:
                overrides += 'RXVMHSTART=test\n'
            fixture = Fixture(overrides=overrides, state='normal' if recovery else 'exceeded')
            if secondary:
                fixture.payload_for('eth1')
            if recovery:
                (fixture.root / ('tmp/dvm1_eth1_h_bad_rx_notified' if secondary else 'tmp/dvm_h_bad_rx_notified')).touch()
            try:
                fixture.run()
                self.assertIn('VIRSH domif-setlink test vnet0 ' + ('up' if recovery else 'down'), fixture.output())
            finally:
                fixture.close()

    def test_valid_interface_changes_link(self):
        fixture = Fixture(overrides="RXVMHSTOP=valid\n")
        try:
            fixture.run()
            self.assertIn("VIRSH domif-setlink valid vnet0 down", fixture.output())
            self.assertIn("disconnected with success", fixture.output())
        finally:
            fixture.close()


class DiagnosticTests(unittest.TestCase):
    def test_process_discovery_failure_is_not_reported_as_stopped(self):
        fixture = Fixture()
        fixture.script = fixture.script.replace('pgrep() { return 0; }', 'pgrep() { return 2; }')
        try:
            result = fixture.run('--dry-run')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unable to determine', result.stdout.decode())
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_confirmed_stopped_service_remains_a_successful_diagnostic(self):
        fixture = Fixture()
        fixture.script = fixture.script.replace('pgrep() { return 0; }', 'pgrep() { return 1; }')
        try:
            result = fixture.run('--dry-run')
            self.assertEqual(result.returncode, 0)
            self.assertIn('not running', result.stdout.decode())
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_dry_run_never_executes_actions_or_changes_markers(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\nRXVMHSTOP=test\n')
        try:
            result = fixture.run('--dry-run')
            self.assertEqual(fixture.output(), '')
            self.assertFalse((fixture.root / 'tmp/dvm_h_bad_rx_notified').exists())
            self.assertIn('DRY RUN', result.stdout.decode())
        finally:
            fixture.close()

    def test_dry_run_does_not_source_user_code(self):
        fixture = Fixture()
        (fixture.root / 'absent').write_text(f'echo USER-CODE >> "{fixture.record.as_posix()}"\n')
        try:
            fixture.run('--dry-run')
            self.assertEqual(fixture.output(), '')
        finally:
            fixture.close()

    def test_dry_run_preserves_disabled_and_recovery_state(self):
        for overrides, state in [('RXLIMITH=-1\n', 'exceeded'), ('GOODACTIONS=enable\nRXDOCKERHSTART=test\n', 'normal')]:
            fixture = Fixture(overrides=overrides, state=state)
            marker = fixture.root / 'tmp/dvm_h_bad_rx_notified'
            marker.touch()
            try:
                fixture.run('--dry-run')
                self.assertTrue(marker.exists())
                self.assertEqual(fixture.output(), '')
            finally:
                fixture.close()

    def test_manual_check_selects_dry_run(self):
        script = (ROOT / 'source/usr/local/emhttp/plugins/dvm/scripts/manual_check').read_text()
        with tempfile.TemporaryDirectory(prefix='dvm-manual-') as folder:
            record = Path(folder) / 'args'
            script = script.replace('/usr/sbin/dvm-notify', 'notifier')
            prefix = f'find() {{ :; }}\nvnstat() {{ :; }}\nnotifier() {{ printf "%s" "$*" > "{record.as_posix()}"; }}\n'
            subprocess.run([BASH], input=(prefix + script).encode(), capture_output=True, check=True)
            self.assertEqual(record.read_text(), '--dry-run')

    def test_custom_alarm_example_does_nothing_on_unknown(self):
        text = (ROOT / 'source/usr/local/emhttp/plugins/dvm/vnstat/dvm-custom-alarms.sh').read_text()
        example = text[text.index('# STATE='):text.index('# esac') + len('# esac')]
        script = '\n'.join(line[2:] for line in example.splitlines())
        for state, expected in [('error', ''), ('disabled', ''), ('exceeded', 'stop syncthing'), ('normal', 'start syncthing')]:
            with tempfile.TemporaryDirectory(prefix='dvm-example-') as folder:
                record = Path(folder) / 'actions'
                prefix = f'php() {{ echo {state}; }}\nlogger() {{ cat >/dev/null; }}\ndocker() {{ printf "%s" "$*" > "{record.as_posix()}"; }}\n'
                subprocess.run([BASH], input=(prefix + script).encode(), capture_output=True, check=True)
                self.assertEqual(record.read_text() if record.exists() else '', expected)


class OutcomeTests(unittest.TestCase):
    def test_completion_write_failure_is_not_automatically_replayed(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n')
        helper = fixture.root / 'outcome.php'
        helper.write_text(helper.read_text().replace('dvm_outcome_record($operation, $argv[2]', "if ($operation === 'finish') { throw new RuntimeException('fixture completion write failed'); }\n            dvm_outcome_record($operation, $argv[2]"))
        try:
            self.assertNotEqual(fixture.run().returncode, 0)
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['phase'], 'started')
            self.assertFalse(fixture.outcomes()[0]['retryable'])
            fixture.run()
            self.assertNotEqual(fixture.run('--retry', 'primary-h-rx').returncode, 0)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            fixture.close()

    def test_verified_action_snapshot_executes_and_is_removed(self):
        fixture = Fixture()
        (fixture.root / 'absent').write_text('hour_rx_reached() { echo ORIGINAL >> "$RECORD"; }\n')
        try:
            self.assertEqual(fixture.run().returncode, 0)
            self.assertIn('ORIGINAL', fixture.output())
            self.assertEqual(list((fixture.root / 'tmp').glob('dvm-actions.*')), [])
        finally:
            fixture.close()

    def test_script_replaced_during_slow_workload_is_not_sourced(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', slow=True)
        actions = fixture.root / 'absent'
        actions.write_text('hour_rx_reached() { echo ORIGINAL >> "$RECORD"; }\n')
        try:
            with ThreadPoolExecutor() as pool:
                future = pool.submit(fixture.run)
                deadline = time.monotonic() + 5
                while 'DOCKER' not in fixture.output() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertIn('DOCKER', fixture.output())
                actions.write_text('echo REPLACED-TOP-LEVEL >> "$RECORD"\nhour_rx_reached() { echo REPLACED-FUNCTION >> "$RECORD"; }\n')
                result = future.result()
            self.assertNotIn('REPLACED', fixture.output())
            self.assertNotIn('ORIGINAL', fixture.output())
            self.assertNotEqual(result.returncode, 0)
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['components']['docker']['code'], 0)
            self.assertEqual(record['components']['custom']['code'], 75)
        finally:
            fixture.close()

    def test_failed_script_load_blocks_partial_functions_in_later_rules(self):
        fixture = Fixture(overrides='TXLIMITH=1\nTXUNITH=B\n')
        (fixture.root / 'absent').write_text('hour_tx_reached() { echo PARTIAL >> "$RECORD"; }\nreturn 42\n')
        runner = fixture.root / 'runner.php'
        text = runner.read_text().replace('function ($command) { return [file_get_contents(__DIR__', 'function ($command) use ($args) { $payload = json_decode(file_get_contents(__DIR__')
        # Return a valid per-direction backend fixture for both hourly rules.
        text = text.replace(".'/query.json'), 0];", ".'/query.json'), true); $payload['interfaces'][0]['alert']['limit']['condition'] = $args[4]; return [json_encode($payload), 0];")
        runner.write_text(text)
        try:
            fixture.run()
            self.assertNotIn('PARTIAL', fixture.output())
            for mode in ['rx', 'tx']:
                record = json.loads((fixture.root / f'outcomes/primary-h-{mode}.json').read_text())
                self.assertEqual(record['components']['custom']['code'], 42)
        finally:
            fixture.close()

    def test_user_script_load_failure_records_actual_exit_status(self):
        fixture = Fixture()
        (fixture.root / 'absent').write_text('return 42\n')
        try:
            fixture.run()
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['components']['custom']['code'], 42)
            self.assertIn('status 42', record['components']['custom']['reason'])
        finally:
            fixture.close()

    def test_notification_only_retry_skips_successful_workloads(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', notification_status=1)
        try:
            fixture.run()
            fixture.script = fixture.script.replace('return 1; }\ndocker()', 'return 0; }\ndocker()')
            result = fixture.run('--retry', 'primary-h-rx')
            self.assertEqual(result.returncode, 0)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
            self.assertEqual(fixture.output().count('NOTIFY'), 2)
        finally:
            fixture.close()

    def test_secondary_retry_uses_current_selected_rule(self):
        fixture = Fixture(overrides='RXLIMITH=-1\nCUSTOM6INTERFACE=eth1\nCUSTOM6LIMIT=1\nCUSTOM6UNIT=B\nCUSTOM6STOP=test\n', docker_status=1)
        fixture.payload_for('eth1')
        try:
            fixture.run()
            fixture.script = fixture.script.replace('return 1; }\nvirsh()', 'return 0; }\nvirsh()')
            self.assertEqual(fixture.run('--retry', 'secondary-6').returncode, 0)
            record = json.loads((fixture.root / 'outcomes/secondary-6.json').read_text())
            self.assertEqual(record['status'], 'success')
            self.assertEqual(record['attempts'], 2)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 2)
        finally:
            fixture.close()

    @unittest.skipIf(os.name == 'nt', 'Requires Linux process groups and real flock')
    def test_interrupted_attempt_is_visible_and_not_replayed(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', slow=True)
        process = subprocess.Popen([BASH, '-s'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            process.stdin.write(fixture.script.encode()); process.stdin.close()
            deadline = time.monotonic() + 5
            while 'DOCKER' not in fixture.output() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIn('DOCKER', fixture.output())
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['phase'], 'started')
            self.assertEqual(fixture.outcomes()[0]['status'], 'running')
            self.assertFalse(fixture.outcomes()[0]['retryable'])
            fixture.run()
            self.assertNotEqual(fixture.run('--retry', 'primary-h-rx').returncode, 0)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM); process.wait(timeout=5)
            process.stdout.close(); process.stderr.close()
            fixture.close()

    def test_unwritable_ledger_prevents_workload_actions(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n')
        (fixture.root / 'outcomes').write_text('not a directory')
        try:
            result = fixture.run()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(fixture.output(), '')
            self.assertFalse((fixture.root / 'tmp/dvm_h_bad_rx_notified').exists())
        finally:
            fixture.close()

    def test_failed_action_is_recorded_without_automatic_retry(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', docker_status=1)
        try:
            fixture.run(); fixture.run()
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['components']['docker']['code'], 1)
            self.assertIn('status 1', record['components']['docker']['reason'])
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            fixture.close()

    def test_explicit_retry_only_repeats_failed_component(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', docker_status=1)
        fixture.script = fixture.script.replace('hour_rx_reached() { return 0; }', 'hour_rx_reached() { echo CUSTOM >> "$RECORD"; return 0; }')
        try:
            fixture.run()
            fixture.script = fixture.script.replace('return 1; }\nvirsh()', 'return 0; }\nvirsh()')
            result = fixture.run('--retry', 'primary-h-rx')
            self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
            record = json.loads((fixture.root / 'outcomes/primary-h-rx.json').read_text())
            self.assertEqual(record['status'], 'success')
            self.assertEqual(record['attempts'], 2)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 2)
            self.assertEqual(fixture.output().count('CUSTOM'), 1)
            self.assertEqual(fixture.output().count('NOTIFY'), 1)
        finally:
            fixture.close()

    def test_retry_rejects_changed_configuration_or_action_script(self):
        for target in ['config', 'absent']:
            fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', docker_status=1)
            try:
                fixture.run()
                with (fixture.root / target).open('a') as output:
                    output.write('\n# changed after failure\n')
                result = fixture.run('--retry', 'primary-h-rx')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
            finally:
                fixture.close()

    def test_retry_rejects_changed_threshold_state(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', docker_status=1)
        try:
            fixture.run()
            path = fixture.root / 'query.json'
            data = json.loads(path.read_text())
            data['interfaces'][0]['alert']['limit']['exceeded'] = False
            path.write_text(json.dumps(data))
            result = fixture.run('--retry', 'primary-h-rx')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            fixture.close()

    def test_status_is_read_only_and_strips_untrusted_fields(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n', docker_status=1)
        try:
            fixture.run()
            path = fixture.root / 'outcomes/primary-h-rx.json'
            data = json.loads(path.read_text())
            data['secret'] = 'DO NOT EXPOSE'
            data['components']['docker']['reason'] = '<script>DO NOT EXPOSE</script>'
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            outcomes = fixture.outcomes()
            self.assertEqual(len(outcomes), 1)
            self.assertTrue(outcomes[0]['retryable'])
            self.assertNotIn('DO NOT EXPOSE', json.dumps(outcomes))
            self.assertNotIn('fingerprint', outcomes[0])
            self.assertEqual(before, path.read_bytes())
        finally:
            fixture.close()

    def test_dry_run_creates_no_outcome_records(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n')
        try:
            fixture.run('--dry-run')
            self.assertFalse((fixture.root / 'outcomes').exists())
        finally:
            fixture.close()

    def test_retry_rejects_success_and_invalid_tokens(self):
        fixture = Fixture(overrides='RXDOCKERHSTOP=test\n')
        try:
            fixture.run()
            for token in ['primary-h-rx', '../anything', 'secondary-7', 'primary-h-rx;touch']:
                self.assertNotEqual(fixture.run('--retry', token).returncode, 0)
            self.assertEqual(fixture.output().count('DOCKER stop test'), 1)
        finally:
            fixture.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['threshold', 'concurrency', 'vm', 'diagnostic', 'outcomes'])
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase({'threshold': ThresholdTests, 'concurrency': ConcurrencyTests, 'vm': VmTests, 'diagnostic': DiagnosticTests, 'outcomes': OutcomeTests}[args.group])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
