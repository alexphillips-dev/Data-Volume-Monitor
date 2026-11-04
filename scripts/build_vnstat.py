#!/usr/bin/env python3
"""Build the pinned vnStat dependency on Linux without installing into the host."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

from build_package import publish_outputs

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.14'
PACKAGE = f'vnstat-{VERSION}-x86_64-1_dvm.txz'
SIGNER = '23EF1DD76E65248FB055201ADAFE84E63D140114'
SOURCE_SHA256 = '8ba2119b3c6f780775135f9c9fa7236867da67e2f93649f1313319b9cf48f87c'
INPUTS = {
    'zig.tar.xz': ('https://ziglang.org/download/0.13.0/zig-linux-x86_64-0.13.0.tar.xz',
                   'd45312e61ebcc48032b77bc4cf7fd6915c11fa16e4aad116b66c9468211230ea'),
    'gd.txz': ('https://slackware.uk/slackware/slackware64-14.2/slackware64/l/gd-2.2.1-x86_64-1.txz',
               'a933c3b3e70e59b42c66a1cfe233d3808b6d0c97de4a77de15fd6420879e91a0'),
    'sqlite.txz': ('https://slackware.uk/slackware/slackware64-14.2/slackware64/ap/sqlite-3.13.0-x86_64-1.txz',
                   '0c54faf804b26a44ae7cf6c5fcd9ada1af38908a101ce1e6795bd1136ee68ecf'),
}


def checked_bytes(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Input checksum mismatch: {path.name}')
    return data


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def inspect_binary(path):
    dynamic = run(['readelf', '-d', str(path)], capture_output=True, text=True).stdout
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise ValueError('Build paths must not be embedded in the dependency')
    needed = sorted(re.findall(r'Shared library: \[([^]]+)\]', dynamic))
    allowed = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libsqlite3.so.0'}
    if path.name == 'vnstati':
        allowed.add('libgd.so.3')
    if not set(needed) <= allowed or 'libsqlite3.so.0' not in needed:
        raise ValueError(f'Unexpected runtime libraries: {needed}')
    if path.name == 'vnstati' and 'libgd.so.3' not in needed:
        raise ValueError('Image output support was not built')
    versions = run(['readelf', '--version-info', str(path)], capture_output=True, text=True).stdout
    glibc = [tuple(map(int, x.split('.'))) for x in re.findall(r'GLIBC_([0-9.]+)', versions)]
    if not glibc or max(glibc) > (2, 17):
        raise ValueError('Dependency exceeds the GLIBC 2.17 build target')
    header = run(['readelf', '-h', str(path)], capture_output=True, text=True).stdout
    if 'Advanced Micro Devices X86-64' not in header:
        raise ValueError('Dependency must target x86_64')
    return {'needed': needed, 'maximum_glibc_symbol': '.'.join(map(str, max(glibc))),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build(cache):
    sources = ROOT / 'packages/sources'
    source = sources / f'vnstat-{VERSION}.tar.gz'
    checked_bytes(source, SOURCE_SHA256)
    cache.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in INPUTS.items():
        destination = cache / name
        if not destination.exists():
            data = urllib.request.urlopen(url, timeout=120).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'Download checksum mismatch: {name}')
            destination.write_bytes(data)
        checked_bytes(destination, digest)
    # Build only in a fresh isolated directory. No make install or host service
    # command is used, and no database/configuration is placed into the payload.
    with tempfile.TemporaryDirectory(prefix='build-', dir=cache) as folder:
        stage = Path(folder)
        gnupg = stage / 'gpg'
        gnupg.mkdir(mode=0o700)
        run(['gpg', '--homedir', str(gnupg), '--batch', '--import', str(sources / 'vnstat-author.asc')], capture_output=True)
        signature = run(['gpg', '--homedir', str(gnupg), '--batch', '--status-fd=1', '--verify',
                         str(source) + '.asc', str(source)], capture_output=True, text=True)
        if f'VALIDSIG {SIGNER} ' not in signature.stdout:
            raise ValueError('Unexpected upstream source signer')
        for archive in [source, cache / 'zig.tar.xz']:
            with tarfile.open(archive) as tar:
                tar.extractall(stage, filter='data')
        include = stage / 'sysroot/usr/include'
        lib = stage / 'sysroot/usr/lib64'
        lib.mkdir(parents=True)
        libraries = {'gd.txz': ('libgd.so', 'libgd.so.3.0.20201'),
                     'sqlite.txz': ('libsqlite3.so', 'libsqlite3.so.0.8.6')}
        for name, (link, target) in libraries.items():
            with tarfile.open(cache / name) as tar:
                for member in tar:
                    if member.isfile() and member.name.startswith('usr/include/'):
                        tar.extract(member, stage / 'sysroot', filter='data')
                (lib / target).write_bytes(tar.extractfile('usr/lib64/' + target).read())
            (lib / link).symlink_to(target)
        zig = stage / 'zig-linux-x86_64-0.13.0/zig'
        src = stage / f'vnstat-{VERSION}'
        env = os.environ.copy()
        # Avoid inheriting local include/library overrides or optional test
        # detection. Tests run independently against the packaged executables.
        for key in ['CPATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'LD_LIBRARY_PATH', 'LIBS', 'CPPFLAGS', 'PKG_CONFIG_PATH']:
            env.pop(key, None)
        env.update(CC=shlex.join([str(zig), 'cc', '-target', 'x86_64-linux-gnu.2.17', '-mcpu=baseline']),
                   CFLAGS=shlex.join(['-O2', '-fstack-protector-strong', f'-ffile-prefix-map={stage}=.', f'-I{include}']),
                   LDFLAGS=shlex.join([f'-L{lib}', '-Wl,--allow-shlib-undefined', '-Wl,-z,relro,-z,now', '-s']),
                   SOURCE_DATE_EPOCH='0', LC_ALL='C', TZ='UTC', PKG_CONFIG='/bin/false')
        with (stage / 'build.log').open('w') as log:
            try:
                run(['./configure', '--prefix=/usr', '--sysconfdir=/etc', '--localstatedir=/var', '--disable-extra-paths'],
                    cwd=src, env=env, stdout=log, stderr=subprocess.STDOUT)
                run(['make', '-j2'], cwd=src, env=env, stdout=log, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print((stage / 'build.log').read_text()[-6000:], file=sys.stderr)
                raise
        files = {}
        binaries = {}
        for name, directory in [('vnstat', 'bin'), ('vnstatd', 'sbin'), ('vnstati', 'bin')]:
            binaries[name] = inspect_binary(src / name)
            files[f'usr/{directory}/{name}'] = ((src / name).read_bytes(), 0o755)
        doc = f'usr/doc/vnstat-{VERSION}'
        for name in ['COPYING', 'CHANGES', 'README', 'INSTALL', 'UPGRADE', 'FAQ']:
            files[f'{doc}/{name}'] = ((src / name).read_bytes(), 0o644)
        for name in ['vnstat.1', 'vnstati.1', 'vnstatd.8', 'vnstat.conf.5']:
            files[f'usr/man/man{name[-1]}/{name}'] = ((src / 'man' / name).read_bytes(), 0o644)
        files['install/slack-desc'] = ((
            'vnstat: vnStat (network traffic monitor)\n'
            'vnstat:\n'
            'vnstat: vnstat, vnstatd and vnstati version 2.14 by Teemu Toivola.\n'
            'vnstat: Packaged from signed upstream source by alexphillips-dev for DVM.\n'
            'vnstat: x86_64 baseline, GLIBC <= 2.17 target, SQLite 3 and LibGD 3 ABI.\n'
            'vnstat: Existing configuration and databases are managed by DVM.\n'
            'vnstat: https://humdi.net/vnstat/\n'
        ).encode(), 0o644)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:xz', format=tarfile.USTAR_FORMAT) as tar:
            for name, (data, mode) in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.uid = entry.gid = entry.mtime = 0
                entry.uname = entry.gname = 'root'
                entry.mode = mode
                entry.size = len(data)
                tar.addfile(entry, io.BytesIO(data))
        data = buffer.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        metadata = {'version': VERSION, 'source_url': f'https://humdi.net/vnstat/vnstat-{VERSION}.tar.gz',
                    'source_sha256': SOURCE_SHA256, 'source_signer': SIGNER,
                    'toolchain': 'Zig 0.13.0 / LLVM 18', 'target': 'x86_64-linux-gnu.2.17 baseline',
                    'configure': ['--prefix=/usr', '--sysconfdir=/etc', '--localstatedir=/var', '--disable-extra-paths'],
                    'build_inputs': {name: {'url': url, 'sha256': sha} for name, (url, sha) in INPUTS.items()},
                    'binaries': binaries, 'package': PACKAGE, 'sha256': digest}
        output = ROOT / 'packages' / PACKAGE
        publish_outputs({output: data,
                         Path(str(output) + '.sha256'): f'{digest}  {PACKAGE}\n'.encode(),
                         Path(str(output) + '.md5'): f'{hashlib.md5(data).hexdigest()}  {PACKAGE}\n'.encode(),
                         ROOT / f'packages/vnstat-{VERSION}-build.json': (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode()})
        print(f'Built {PACKAGE}\nSHA256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/dvm-vnstat-build')
    options = parser.parse_args()
    if sys.platform != 'linux' or sys.version_info < (3, 12) or not all(shutil.which(name) for name in ['make', 'gpg', 'readelf']):
        parser.error('Requires Linux, Python 3.12+, make, gpg and readelf; builds do not require root')
    build(options.cache.resolve())
