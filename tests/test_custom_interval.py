"""Exercise the generated 45-minute schedule across hour boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = r"C:\Program Files\Git\bin\bash.exe" if __import__("os").name == "nt" else "bash"


class CustomIntervalTests(unittest.TestCase):
    def test_45_minute_schedule_has_no_15_minute_gap(self):
        rc = (ROOT / "source/etc/rc.d/rc.vnstat").read_text()
        branch = rc.split('elif [ "$CRONINT" == "45min" ]; then', 1)[1].split('elif [ "$CRONINT" == "60min" ]; then', 1)[0]
        with tempfile.TemporaryDirectory(prefix="dvm-interval-test-") as folder:
            cron = Path(folder) / "custom.cron"
            cron.write_bytes((ROOT / "source/usr/local/emhttp/plugins/dvm/misc/dvm-custom-alarms.cron").read_bytes())
            branch = branch.replace('/boot/config/plugins/dynamix/dvm-custom-alarms.cron', '"' + cron.as_posix() + '"')
            result = subprocess.run([BASH], input="sleep() { :; }\n" + branch, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            line = next(line for line in cron.read_text().splitlines() if line and not line.startswith('#'))
            runs = []
            if 'run_custom_alarms_45' in line:
                action = Path(folder) / "action"
                action.write_text('#!/bin/bash\necho ACTION\n', newline='\n')
                action.chmod(0o755)
                helper = (ROOT / "source/usr/local/emhttp/plugins/dvm/scripts/run_custom_alarms_45").read_text()
                helper = helper.replace('/etc/vnstat/dvm-custom-alarms.sh', '"' + action.as_posix() + '"')
                for minute in [0, 15, 30, 44, 45, 59, 60, 89, 90, 105, 120, 134, 135, 179, 180]:
                    result = subprocess.run([BASH], input=f'date() {{ echo {minute*60}; }}\n' + helper, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if 'ACTION' in result.stdout:
                        runs.append(minute)
            else:
                step = int(line.split()[0].removeprefix('*/'))
                runs = [minute for minute in range(181) if minute % 60 % step == 0]
            self.assertEqual(runs, [0, 45, 90, 135, 180])


if __name__ == "__main__":
    unittest.main()
