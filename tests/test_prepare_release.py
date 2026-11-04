"""Release preparation must isolate channels and preserve existing deliverables."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class PrepareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dvm-release-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'checkout'
        self.root.mkdir()
        for name in ['source', 'plugin', 'packages', 'scripts']:
            shutil.copytree(ROOT / name, self.root / name)
        for name in ['.gitignore', '.gitattributes']:
            shutil.copyfile(ROOT / name, self.root / name)
        channel = runpy.run_path(str(ROOT / 'scripts/release_channel.py'))
        manifest = self.root / 'plugin/dvm.plg'
        manifest.write_text(channel['render_manifest'](manifest.read_text(), 'dev', '2026.11.04.08'))
        self.metadata = self.root / 'source' / channel['RELEASE_METADATA_REL']
        self.metadata.write_text(json.dumps(channel['release_metadata']('dev', '2026.11.04.08')) + '\n')
        build = runpy.run_path(str(self.root / 'scripts/build_package.py'))['main']
        build.__globals__.update(ROOT=self.root, SOURCE=self.root / 'source', MANIFEST=manifest)
        with contextlib.redirect_stdout(io.StringIO()): build()
        subprocess.run(['git', 'init', '--quiet', '--initial-branch=dev'], cwd=self.root, check=True)
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True, capture_output=True)
        namespace = runpy.run_path(str(ROOT / 'scripts/prepare_release.py'))
        self.prepare = namespace['prepare_release']

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for folder in ['source', 'archive', 'plugin'] for path in (self.root / folder).rglob('*') if path.is_file()}

    def run_prepare(self, channel='main', version='2026.11.04.09', **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.prepare(self.root, channel, version, **kwargs)

    def test_dry_run_builds_both_exact_channels_without_mutating_checkout(self):
        before = self.snapshot()
        for channel in ['dev', 'main']:
            result = self.run_prepare(channel=channel)
            self.assertEqual(result['channel'], channel)
            self.assertIn('/' + channel + '/plugin/dvm.plg', result['plugin_url'])
            self.assertEqual(result['package_validation'], 'passed')
            self.assertEqual(result['mode'], 'dry-run')
            self.assertEqual(len(result['sha256']), 64)
        self.assertEqual(self.snapshot(), before)

    def test_output_stable_candidate_preserves_source_and_has_matching_metadata(self):
        before = self.snapshot()
        output = self.folder / 'stable-candidate'
        self.run_prepare(output=output)
        metadata = json.loads((output / 'source/usr/local/emhttp/plugins/dvm/release.json').read_text())
        self.assertEqual(metadata['channel'], 'main')
        self.assertEqual(metadata['version'], '2026.11.04.09')
        self.assertEqual(self.snapshot(), before)
        validator = runpy.run_path(str(output / 'scripts/validate_repository.py'))
        with contextlib.redirect_stdout(io.StringIO()): validator['check_package'](output, 'main')
        with self.assertRaises(ValueError): validator['check_package'](output, 'dev')

    def test_apply_dev_changes_only_generated_release_files(self):
        original_config = (self.root / 'source/usr/local/emhttp/plugins/dvm/default.cfg').read_bytes()
        original_install = (self.root / 'source/install/doinst.sh').read_bytes()
        result = self.run_prepare(channel='dev', apply=True)
        self.assertEqual(result['mode'], 'apply')
        self.assertEqual(json.loads(self.metadata.read_text())['version'], '2026.11.04.09')
        self.assertEqual((self.root / 'source/usr/local/emhttp/plugins/dvm/default.cfg').read_bytes(), original_config)
        self.assertEqual((self.root / 'source/install/doinst.sh').read_bytes(), original_install)
        self.assertTrue((self.root / 'archive/dvm-2026.11.04.08-x86_64-1.txz').is_file())

    def test_apply_cannot_change_main_from_dev_or_dev_from_main(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'matching'):
            self.run_prepare(channel='main', apply=True)
        subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], cwd=self.root, check=True)
        with self.assertRaisesRegex(ValueError, 'matching'):
            self.run_prepare(channel='dev', apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_channel_switch_candidates_keep_identity_and_configuration(self):
        stable = self.folder / 'stable'
        self.run_prepare(output=stable)
        development = self.folder / 'development'
        with contextlib.redirect_stdout(io.StringIO()):
            self.prepare(stable, 'dev', '2026.11.04.10', output=development)
        self.assertEqual(json.loads((development / 'source/usr/local/emhttp/plugins/dvm/release.json').read_text())['channel'], 'dev')
        import xml.etree.ElementTree as ET
        for candidate in [stable, development]:
            self.assertEqual(ET.parse(candidate / 'plugin/dvm.plg').getroot().attrib['name'], 'dvm')
            self.assertEqual((candidate / 'source/usr/local/emhttp/plugins/dvm/default.cfg').read_bytes(),
                             (self.root / 'source/usr/local/emhttp/plugins/dvm/default.cfg').read_bytes())

    def test_dev_metadata_is_restored_after_stable_back_sync(self):
        stable = self.folder / 'back-sync'
        self.run_prepare(output=stable)
        subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/dev'], cwd=stable, check=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.prepare(stable, 'dev', '2026.11.04.10', apply=True)
        metadata = json.loads((stable / 'source/usr/local/emhttp/plugins/dvm/release.json').read_text())
        self.assertEqual(metadata['channel'], 'dev')
        self.assertEqual(metadata['version'], '2026.11.04.10')
        self.assertIn('/dev/plugin/dvm.plg', metadata['plugin_url'])
        validator = runpy.run_path(str(stable / 'scripts/validate_repository.py'))
        with contextlib.redirect_stdout(io.StringIO()): validator['check_package'](stable, 'dev')

    def test_equal_older_unpadded_and_invalid_versions_are_rejected(self):
        before = self.snapshot()
        for version in ['2026.11.04.08', '2026.11.04.07', '2026.11.04.9', '2026.02.30.09', '2026.11.04.09-dev']:
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.run_prepare(version=version)
        self.assertEqual(self.snapshot(), before)

    def test_existing_or_workspace_output_is_never_overwritten(self):
        output = self.folder / 'existing'
        output.mkdir()
        (output / 'keep').write_bytes(b'keep')
        for target in [output, self.root, self.root / 'candidate']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.run_prepare(output=target)
        self.assertEqual((output / 'keep').read_bytes(), b'keep')

    def test_existing_archive_version_cannot_be_replaced(self):
        archive = self.root / 'archive/dvm-2026.11.04.09-x86_64-1.txz'
        archive.write_bytes(b'prior deliverable')
        with self.assertRaisesRegex(ValueError, 'newer'):
            self.run_prepare(channel='dev', apply=True)
        self.assertEqual(archive.read_bytes(), b'prior deliverable')

    def test_failed_candidate_validation_leaves_checkout_unchanged(self):
        (self.root / 'plugin/dvm.png').write_bytes(b'invalid fixture icon')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'icons differ'):
            self.run_prepare(channel='dev', apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_failed_apply_rolls_back_all_generated_outputs(self):
        before = self.snapshot()
        replace = os.replace
        failed = False
        def fault(source, target):
            nonlocal failed
            if Path(target) == self.metadata and not failed:
                failed = True
                raise OSError('simulated metadata publication failure')
            return replace(source, target)
        with mock.patch.object(os, 'replace', fault), self.assertRaises(OSError):
            self.run_prepare(channel='dev', apply=True)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)

    def run_with_concurrent_change(self, mutate):
        original = runpy.run_path
        injected = False
        def after_candidate_validation(path, *arguments, **kwargs):
            nonlocal injected
            if Path(path) == self.root / 'scripts/build_package.py' and not injected:
                injected = True
                mutate()
            return original(path, *arguments, **kwargs)
        with mock.patch.object(runpy, 'run_path', after_candidate_validation):
            with self.assertRaisesRegex(ValueError, 'changed|concurrent|branch|matching'):
                self.run_prepare(channel='dev', apply=True)
        self.assertTrue(injected, 'Fixture must mutate after candidate validation and before publication')

    def test_concurrent_manifest_edit_is_preserved_and_apply_aborts(self):
        before = self.snapshot()
        relative = 'plugin/dvm.plg'
        edited = before[relative] + b'\n<!-- independently edited release notes -->\n'
        self.run_with_concurrent_change(lambda: (self.root / relative).write_bytes(edited))
        before[relative] = edited
        self.assertEqual(self.snapshot(), before)

    def test_concurrent_release_metadata_edit_is_preserved_and_apply_aborts(self):
        before = self.snapshot()
        relative = self.metadata.relative_to(self.root).as_posix()
        edited = before[relative] + b'\n'
        self.run_with_concurrent_change(lambda: self.metadata.write_bytes(edited))
        before[relative] = edited
        self.assertEqual(self.snapshot(), before)

    def test_branch_switch_before_publication_aborts_apply(self):
        before = self.snapshot()
        def switch_branch():
            subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], cwd=self.root, check=True)
        self.run_with_concurrent_change(switch_branch)
        self.assertEqual(self.snapshot(), before)
        branch = subprocess.check_output(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=self.root, text=True).strip()
        self.assertEqual(branch, 'main', 'Preparation must not reverse an independent branch change')

    def test_ignored_source_created_during_preparation_is_preserved_and_apply_aborts(self):
        before = self.snapshot()
        before['source/.env'] = b'private fixture\n'
        self.run_with_concurrent_change(lambda: (self.root / 'source/.env').write_bytes(before['source/.env']))
        self.assertEqual(self.snapshot(), before)

    def test_candidate_index_preserves_tracked_and_intended_untracked_modes(self):
        folder = self.root / 'mode-fixtures'
        folder.mkdir()
        files = {'tracked-normal': (b'normal\n', 0o755, '100644'),
                 'tracked-executable': (b'#!/bin/sh\nexit 0\n', 0o644, '100755'),
                 'untracked-normal': (b'normal\n', 0o755, '100644'),
                 'untracked-script': (b'#!/bin/sh\nexit 0\n', 0o644, '100755')}
        for name, (contents, mode, expected) in files.items():
            path = folder / name
            path.write_bytes(contents)
            path.chmod(mode)
            if name.startswith('tracked-'):
                subprocess.run(['git', 'add', str(path)], cwd=self.root, check=True)
                subprocess.run(['git', 'update-index', '--chmod=' + ('+x' if expected == '100755' else '-x'),
                                str(path)], cwd=self.root, check=True)
        output = self.folder / 'mode-candidate'
        self.run_prepare(output=output)
        for name, (_, _, expected) in files.items():
            actual = subprocess.check_output(['git', 'ls-files', '--stage', '--', 'mode-fixtures/' + name],
                                             cwd=output, text=True).split()[0]
            self.assertEqual(actual, expected, name + ' must have the intended Git mode independent of host mode bits')

    def test_ignored_source_input_rejects_preparation_without_changes(self):
        (self.root / 'source/.env').write_bytes(b'FIXTURE_ONLY=yes\n')
        before = self.snapshot()
        output = self.folder / 'ignored-source-candidate'
        for mode in [{}, {'output': output}, {'apply': True}]:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, '[Ii]gnored.*source|source.*[Ii]gnored'):
                    self.run_prepare(channel='dev', **mode)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(output.exists(), 'Rejected input must not publish a candidate directory')


if __name__ == '__main__':
    unittest.main()
