"""Exercise the real matching script with command mocks and isolated proc/sys fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'source/usr/local/emhttp/plugins/dvm/scripts/match_virts'
BASH = str(Path('C:/Program Files/Git/bin/bash.exe')) if Path('C:/Program Files/Git/bin/bash.exe').exists() else shutil.which('bash')


class MatchingTests(unittest.TestCase):
    def run_script(self, peer_lines):
        with tempfile.TemporaryDirectory(prefix='dvm-match-') as directory:
            root = Path(directory)
            proc = root / 'proc/123/net'
            proc.mkdir(parents=True)
            (proc / 'igmp').write_text('Idx Device : Count Querier\n2 eth0 : 1 V3\n', encoding='utf-8')
            network = root / 'sys/class/net'
            network.mkdir(parents=True)
            for name in ['vethRIGHT', 'vethWRONG', 'vnet0', 'vnet1', 'br-fixture']:
                (network / name).touch()
            (root / 'ip-output').write_text(peer_lines, encoding='utf-8')
            # Change only the read-only host paths in the test copy, never production source.
            script = SOURCE.read_text().replace('/proc/', root.as_posix() + '/proc/').replace('/sys/class/net/', network.as_posix() + '/')
            mocks = '''
docker() {
    case "$1 $2" in
        'ps --format') printf '%s\\n' 'test-container' ;;
        'inspect test-container') printf '%s\\n' 123 ;;
        'network ls') printf '%s\\n' fixture ;;
        'network inspect') printf '%s\\n' test-container ;;
    esac
}
ip() { cat "$DVM_FIXTURE/ip-output"; }
virsh() {
    if [ "$1" = list ]; then
        printf '%s\\n' 'Windows 11' 'ordinary-vm'
    elif [ "$1" = domiflist ]; then
        printf '%s\\n' header separator
        case "$2" in
            'Windows 11') printf '%s\\n' 'vnet0 bridge br0 virtio 00:00:00:00:00:00' ;;
            ordinary-vm) printf '%s\\n' 'vnet1 bridge br0 virtio 00:00:00:00:00:01' ;;
        esac
    fi
}
'''
            import os
            environment = dict(os.environ, DVM_FIXTURE=root.as_posix())
            result = subprocess.run([BASH], input=mocks + script, text=True, capture_output=True, env=environment, check=True)
            return result.stdout.splitlines()

    def test_vm_name_with_spaces(self):
        output = self.run_script('vethRIGHT@if2 UP 192.0.2.1\n')
        self.assertIn('vnet0:Windows 11', output)
        self.assertIn('vnet1:ordinary-vm', output)

    def test_exact_index_with_prefix_neighbor(self):
        output = self.run_script('vethRIGHT@if2 UP 192.0.2.1\nvethWRONG@if21 UP 192.0.2.2\n')
        self.assertIn('vethRIGHT:test-container', output)
        self.assertNotIn('vethWRONG:test-container', output)

    def test_index_prefix_alone_is_not_a_match(self):
        output = self.run_script('vethWRONG@if21 UP 192.0.2.2\n')
        self.assertNotIn('vethWRONG:test-container', output)

    def test_existing_exact_and_bridge_mapping(self):
        output = self.run_script('vethRIGHT@if2 UP 192.0.2.1\n')
        self.assertIn('vethRIGHT:test-container', output)
        self.assertIn('br-fixture:test-container', output)


if __name__ == '__main__':
    unittest.main()
