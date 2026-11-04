"""Canonical build-time channel metadata shared by release tools and checks."""
import re
import subprocess
import xml.etree.ElementTree as ET

REPOSITORY_BASE = 'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/'
RELEASE_METADATA_REL = 'usr/local/emhttp/plugins/dvm/release.json'
CHANNELS = ('dev', 'main')


def channel_base(channel):
    if channel not in CHANNELS:
        raise ValueError('Release channel must be dev or main')
    return REPOSITORY_BASE + channel + '/'


def validate_version(version):
    if not isinstance(version, str) or len(version) > 64 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', version):
        raise ValueError('Invalid plugin version')
    return version


def version_key(version):
    return tuple(map(int, validate_version(version).split('.')))


def release_metadata(channel, version):
    return {'schema': 1, 'channel': channel, 'version': validate_version(version),
            'plugin_url': channel_base(channel) + 'plugin/dvm.plg'}


def manifest_channel(text):
    manifest = ET.fromstring(text)
    if manifest.attrib.get('name') != 'dvm':
        raise ValueError('Release must retain the dvm plugin identity')
    for channel in CHANNELS:
        if manifest.attrib.get('pluginURL') == channel_base(channel) + 'plugin/dvm.plg':
            return channel
    raise ValueError('Manifest update URL has an unknown or noncanonical channel')


def expected_channel(root, explicit=None):
    if explicit is not None:
        channel_base(explicit)
        return explicit
    result = subprocess.run(['git', 'symbolic-ref', '--quiet', '--short', 'HEAD'], cwd=root,
                            capture_output=True, text=True)
    branch = result.stdout.strip() if result.returncode == 0 else ''
    if branch not in CHANNELS:
        raise ValueError('Cannot determine expected release channel; pass --channel dev or --channel main')
    return branch


def render_manifest(text, channel, version):
    base = channel_base(channel)
    validate_version(version)
    # Validate the starting identity and channel before changing metadata.
    manifest_channel(text)
    package = re.findall(r'<!ENTITY plgNAME\s+"dvm-[0-9.]+-x86_64-([0-9]+)">', text)
    if len(package) != 1:
        raise ValueError('Expected exactly one dvm package identity')
    values = {'gitURL': base.rstrip('/'), 'version': version,
              'plgNAME': f'dvm-{version}-x86_64-{package[0]}'}
    for entity, value in values.items():
        text, count = re.subn(r'(<!ENTITY ' + entity + r'\s+")[^"]+(">)',
                             lambda match: match[1] + value + match[2], text)
        if count != 1:
            raise ValueError('Expected exactly one ' + entity + ' entity')
    manifest = ET.fromstring(text)
    if manifest_channel(text) != channel:
        raise ValueError('Manifest template has an inconsistent update channel')
    for entry in manifest.findall('FILE'):
        url = entry.findtext('URL')
        if url is not None and not url.startswith(base):
            raise ValueError('Manifest template has an inconsistent download channel')
    return text
