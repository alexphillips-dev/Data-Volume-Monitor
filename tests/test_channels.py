"""Channel metadata, explicit candidate checks and detached CI behavior."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = runpy.run_path(str(ROOT / 'scripts/release_channel.py'))


class ChannelTests(unittest.TestCase):
    def test_only_canonical_supported_channels_are_rendered(self):
        for channel in ['dev', 'main']:
            metadata = CHANNEL['release_metadata'](channel, '2026.11.04.09')
            self.assertEqual(metadata, {'schema':1, 'channel':channel, 'version':'2026.11.04.09',
                'plugin_url':f'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/{channel}/plugin/dvm.plg'})
        for channel in ['', 'stable', 'master', '../main', 'refs/heads/main', 'DEV', None]:
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                CHANNEL['channel_base'](channel)

    def test_render_preserves_plugin_identity_state_paths_and_changelog(self):
        original = (ROOT / 'plugin/dvm.plg').read_text()
        original_xml = ET.fromstring(original)
        for channel in ['dev', 'main']:
            candidate = CHANNEL['render_manifest'](original, channel, '2026.11.04.99')
            parsed = ET.fromstring(candidate)
            self.assertEqual(CHANNEL['manifest_channel'](candidate), channel)
            self.assertEqual(parsed.attrib['name'], 'dvm')
            self.assertEqual(parsed.attrib['version'], '2026.11.04.99')
            self.assertEqual(parsed.findtext('CHANGES'), original_xml.findtext('CHANGES'))
            self.assertEqual([entry.findtext('INLINE') for entry in parsed.findall('FILE')],
                             [entry.findtext('INLINE').replace(original_xml.attrib['version'], '2026.11.04.99')
                              if entry.findtext('INLINE') else None for entry in original_xml.findall('FILE')])
            for entry in parsed.findall('FILE'):
                url = entry.findtext('URL')
                if url:
                    self.assertTrue(url.startswith(CHANNEL['channel_base'](channel)))
            self.assertIn('dvm-2026.11.04.99-x86_64-1', candidate)

    def test_alternate_update_urls_and_changed_identity_are_rejected(self):
        text = (ROOT / 'plugin/dvm.plg').read_text()
        for bad in [text.replace('/Data-Volume-Monitor/dev', '/Data-Volume-Monitor/refs/heads/dev'),
                    text.replace('/Data-Volume-Monitor/main', '/Data-Volume-Monitor/refs/heads/main'),
                    text.replace('name="&name;"', 'name="other"')]:
            if bad == text:
                continue
            with self.assertRaises(ValueError):
                CHANNEL['manifest_channel'](bad)

    def test_unknown_versions_and_mixed_template_downloads_are_rejected(self):
        text = (ROOT / 'plugin/dvm.plg').read_text()
        for version in ['', '2026-dev', '1/../2', '1.2\n', '1.' * 40 + '1', None]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                CHANNEL['render_manifest'](text, 'main', version)
        mixed = text.replace('<URL>&pkgURL;/', '<URL>https://example.invalid/packages/')
        with self.assertRaisesRegex(ValueError, 'download channel'):
            CHANNEL['render_manifest'](mixed, 'main', '2026.11.04.99')

    def test_main_and_dev_context_can_be_inferred_but_not_unknown_or_detached(self):
        with tempfile.TemporaryDirectory(prefix='dvm-channel-context-') as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '--quiet', '--initial-branch=dev'], cwd=root, check=True)
            self.assertEqual(CHANNEL['expected_channel'](root), 'dev')
            subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], cwd=root, check=True)
            self.assertEqual(CHANNEL['expected_channel'](root), 'main')
            (root / 'fixture').write_text('fixture\n')
            subprocess.run(['git', 'add', 'fixture'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                            'commit', '--quiet', '--no-verify', '-m', 'fixture'], cwd=root, check=True)
            subprocess.run(['git', 'checkout', '--quiet', '--detach'], cwd=root, check=True)
            with self.assertRaisesRegex(ValueError, '--channel'):
                CHANNEL['expected_channel'](root)
            self.assertEqual(CHANNEL['expected_channel'](root, 'main'), 'main')
            subprocess.run(['git', 'checkout', '--quiet', '-b', 'release-candidate'], cwd=root, check=True)
            with self.assertRaisesRegex(ValueError, '--channel'):
                CHANNEL['expected_channel'](root)

    def test_version_order_is_numeric(self):
        self.assertLess(CHANNEL['version_key']('2026.11.04.09'), CHANNEL['version_key']('2026.11.04.10'))

    def test_main_workflow_checks_actual_stable_metadata_explicitly(self):
        workflow = (ROOT / '.github/workflows/validate.yml').read_text()
        self.assertEqual(workflow.count('branches: [main]'), 2)
        self.assertIn('python scripts/validate_repository.py --channel main', workflow)
        self.assertNotIn('branches: [dev]', workflow)


if __name__ == '__main__':
    unittest.main()
