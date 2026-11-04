#!/usr/bin/env python3
"""Prepare and inspect an exact channel candidate; never merge, commit or push."""
import argparse
import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def git(root, *arguments, check=True):
    return subprocess.run(['git', *arguments], cwd=root, check=check, capture_output=True, text=True)


def release_version(root, text, channel, version):
    channel['validate_version'](version)
    if not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}\.\d{2}', version):
        raise ValueError('New release versions must use YYYY.MM.DD.NN with a two-digit build number')
    datetime.datetime.strptime(version[:10], '%Y.%m.%d')
    previous = [ET.fromstring(text).attrib['version']]
    if (root / 'archive').is_dir():
        for archive in (root / 'archive').iterdir():
            match = re.fullmatch(r'dvm-([0-9.]+)-x86_64-[0-9]+\.txz', archive.name)
            if match: previous.append(match[1])
    # Unraid's plugin manager uses string ordering for reinstall decisions.
    # Enforce both orders and refuse replacement of an already-used version.
    if any(version <= old or channel['version_key'](version) <= channel['version_key'](old) for old in previous):
        raise ValueError('Release version must be newer than the current manifest and every existing archive')


def checkout_inputs(root):
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=root, capture_output=True, check=True)
    return sorted(set(result.stdout.decode().split('\0')) - {''})


def checkout_modes(root):
    result = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=root, capture_output=True, check=True)
    modes = {}
    for entry in result.stdout.decode().split('\0'):
        if not entry: continue
        description, name = entry.split('\t', 1)
        mode, _digest, stage = description.split()
        if stage != '0' or mode not in ['100644', '100755']:
            raise ValueError('Resolve unmerged or unsupported index entries before release preparation')
        modes[name] = int(mode[-3:], 8)
    return modes


def check_source_inputs(root, during_apply=False):
    ignored = git(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', 'source').stdout
    if ignored:
        message = ('Ignored source inputs changed during preparation; apply cancelled' if during_apply else
                   'Ignored local files in source must be moved out of the package tree before preparation')
        raise ValueError(message)


def copy_checkout(root, target):
    tracked_modes = checkout_modes(root)
    snapshots, modes = {}, {}
    for name in checkout_inputs(root):
        relative = Path(name)
        source = root / relative
        if relative.is_absolute() or '..' in relative.parts or source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('Candidate contains an unsafe or linked input path')
        if not source.is_file():
            raise ValueError(f'Candidate input is unavailable: {name}')
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        data = destination.read_bytes()
        modes[name] = tracked_modes.get(name, 0o755 if data.startswith(b'#!/') else 0o644)
        destination.chmod(modes[name])
        snapshots[name] = hashlib.sha256(data).hexdigest()
    return snapshots, modes


def verify_unchanged(root, snapshots, modes, requested_channel, original):
    check_source_inputs(root, during_apply=True)
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.strip()
    if branch != requested_channel:
        raise ValueError('Checkout branch changed during preparation; apply cancelled')
    if checkout_inputs(root) != sorted(snapshots):
        raise ValueError('Checkout inputs changed during preparation; apply cancelled')
    current_modes = checkout_modes(root)
    for name, digest in snapshots.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('Checkout path changed during preparation; apply cancelled')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest or current_modes.get(name, 0o755 if data.startswith(b'#!/') else 0o644) != modes[name]:
            raise ValueError('Checkout content changed during preparation; apply cancelled')
    if (root / 'plugin/dvm.plg').read_bytes() != original:
        raise ValueError('Manifest changed during preparation; apply cancelled')


def release_notes(text, version, requested_channel, notes):
    if f'###{version}\n' in text:
        if notes is not None:
            raise ValueError('Changelog already contains this release; edit its existing notes before preparation')
        return text
    body = notes if notes is not None else '- release: prepare the ' + ('Stable' if requested_channel == 'main' else 'Development') + ' channel.'
    if not body.strip():
        raise ValueError('Release notes must not be empty')
    entry = f'###{version}\n{html.escape(body.rstrip(), quote=False)}\n'
    text, count = re.subn(r'(<CHANGES>\s*## Data Volume Monitor\n)', lambda match: match[1] + entry, text, count=1)
    if count != 1:
        raise ValueError('Cannot locate the plugin release changelog')
    ET.fromstring(text)
    return text


def prepare_release(root, requested_channel, version, *, output=None, apply=False, notes=None):
    root = Path(root).resolve()
    channel = runpy.run_path(str(root / 'scripts/release_channel.py'))
    base = channel['channel_base'](requested_channel)
    original_bytes = (root / 'plugin/dvm.plg').read_bytes()
    original = original_bytes.decode('utf-8').replace('\r\n', '\n')
    release_version(root, original, channel, version)
    if apply and output is not None:
        raise ValueError('Choose either apply or output mode')
    if apply:
        branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.strip()
        if branch != requested_channel:
            raise ValueError('Apply requires a matching dev/main checkout; use an isolated output for another channel')
    destination = None
    if output is not None:
        supplied = Path(output).expanduser()
        if supplied.is_symlink():
            raise ValueError('Candidate output must not be a link')
        destination = supplied.resolve()
        if destination.is_relative_to(root) or root.is_relative_to(destination) or destination.exists():
            raise ValueError('Candidate output must be a new directory outside the checkout')
        destination.parent.mkdir(parents=True, exist_ok=True)
    validator = runpy.run_path(str(root / 'scripts/validate_repository.py'))
    validator['check_tracked'](root)
    check_source_inputs(root)
    temporary_parent = destination.parent if destination is not None else None
    with tempfile.TemporaryDirectory(prefix='.dvm-prepare-', dir=temporary_parent) as folder:
        candidate = Path(folder) / 'candidate'
        candidate.mkdir()
        snapshots, modes = copy_checkout(root, candidate)
        manifest_path = candidate / 'plugin/dvm.plg'
        rendered = channel['render_manifest'](original, requested_channel, version)
        manifest_path.write_text(release_notes(rendered, version, requested_channel, notes), encoding='utf-8', newline='\n')
        metadata_path = candidate / 'source' / channel['RELEASE_METADATA_REL']
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(channel['release_metadata'](requested_channel, version), indent=2) + '\n',
                                 encoding='utf-8', newline='\n')
        builder = runpy.run_path(str(candidate / 'scripts/build_package.py'))
        build = builder['main']
        build.__globals__.update(ROOT=candidate, SOURCE=candidate / 'source', MANIFEST=manifest_path)
        build()
        # A standalone candidate gets its own local index so the complete
        # validator can run later. No commits, remotes, or pushes are created.
        git(candidate, 'init', '--quiet', '--initial-branch=' + requested_channel)
        git(candidate, '-c', 'core.autocrlf=false', 'add', '--all')
        # DrvFS/Windows stat modes cannot determine repository executable bits.
        # Preserve the source index; generated metadata and archives are 0644.
        for executable, flag in [(True, '--chmod=+x'), (False, '--chmod=-x')]:
            names = [name for name in checkout_inputs(candidate) if (modes.get(name, 0o644) == 0o755) == executable]
            for start in range(0, len(names), 200):
                git(candidate, 'update-index', flag, '--', *names[start:start + 200])
        candidate_validator = runpy.run_path(str(candidate / 'scripts/validate_repository.py'))
        candidate_validator['check_tracked'](candidate)
        candidate_validator['check_package'](candidate, requested_channel)
        manifest = ET.parse(manifest_path).getroot()
        package_name = next(entry.findtext('URL').rsplit('/', 1)[1] for entry in manifest.findall('FILE')
                            if '/archive/' in (entry.findtext('URL') or ''))
        archive_relative = Path('archive') / package_name
        paths = [archive_relative, Path(str(archive_relative) + '.md5'), Path(str(archive_relative) + '.sha256'),
                 Path('source') / channel['RELEASE_METADATA_REL'], Path('plugin/dvm.plg')]
        report = {'channel': requested_channel, 'version': version, 'plugin_url': base + 'plugin/dvm.plg',
                  'package': archive_relative.as_posix(),
                  'sha256': hashlib.sha256((candidate / archive_relative).read_bytes()).hexdigest(),
                  'generated_files': [path.as_posix() for path in paths], 'package_validation': 'passed',
                  'full_regressions': 'run separately against this candidate', 'publication': 'not performed',
                  'mode': 'apply' if apply else ('output' if destination is not None else 'dry-run')}
        if apply:
            publisher = runpy.run_path(str(root / 'scripts/build_package.py'))['publish_outputs']
            publisher.__globals__['ROOT'] = root
            verify_unchanged(root, snapshots, modes, requested_channel, original_bytes)
            release_version(root, original, channel, version)
            for path in paths:
                resolved = root / path
                if resolved.is_symlink() or not resolved.resolve().is_relative_to(root):
                    raise ValueError('Publication path changed during preparation; apply cancelled')
            publisher({root / path: (candidate / path).read_bytes() for path in paths})
        elif destination is not None:
            os.replace(candidate, destination)
            report['output'] = str(destination)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', required=True, choices=['dev', 'main'])
    parser.add_argument('--version', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Build/validate an isolated candidate without publishing it (default)')
    mode.add_argument('--output', type=Path, help='Write a standalone candidate to a new directory outside this checkout')
    mode.add_argument('--apply', action='store_true', help='Publish generated files only in a matching named dev/main checkout')
    parser.add_argument('--notes-file', type=Path, help='UTF-8 Markdown bullets for the new changelog entry')
    options = parser.parse_args()
    notes = options.notes_file.read_text(encoding='utf-8') if options.notes_file else None
    result = prepare_release(ROOT, options.channel, options.version, output=options.output, apply=options.apply, notes=notes)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, ET.ParseError) as error:
        raise SystemExit('Release preparation failed: ' + str(error))
