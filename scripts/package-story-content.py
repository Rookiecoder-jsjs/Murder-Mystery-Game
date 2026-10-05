"""Build immutable signed story bundles; no upload and no model credentials.

Requires OpenSSL. Default is an unsigned local report. A signed release also
requires a fixed source commit which contains exactly the packaged source.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('content_protocol', ROOT / 'backend/app/core/content_protocol.py')
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)
PUBLISHER = 'Rookiecoder-jsjs/Murder-Mystery-Game'


def envelope(payload: dict, domain: str, key: Path, key_id: str) -> dict:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    result = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key)],
                            input=domain.encode() + b'\n' + raw, capture_output=True, check=True)
    return {'envelope_version': 1, 'algorithm': 'SHA256withECDSA', 'key_id': key_id,
            'payload_b64': base64.b64encode(raw).decode(),
            'signature_b64': base64.b64encode(result.stdout).decode()}


def assert_source(path: Path, commit: str) -> None:
    result = subprocess.run(['git', 'show', f'{commit}:{path.relative_to(ROOT).as_posix()}'],
                            cwd=ROOT, capture_output=True, check=True)
    if result.stdout != path.read_bytes():
        raise ValueError(f'固定源码提交与文件不一致：{path.relative_to(ROOT)}')


def verify_envelope(wrapper: dict, domain: str, keys: dict) -> dict:
    if wrapper.get('envelope_version') != 1 or wrapper.get('algorithm') != 'SHA256withECDSA':
        raise ValueError('不支持的签名信封')
    public = keys.get(wrapper.get('key_id'))
    if not public:
        raise ValueError('签名公钥不受信任')
    raw = base64.b64decode(wrapper['payload_b64'], validate=True)
    signature = base64.b64decode(wrapper['signature_b64'], validate=True)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('签名内容超过限制')
    with tempfile.TemporaryDirectory() as directory:
        pub, sig = Path(directory) / 'public.pem', Path(directory) / 'signature.bin'
        pub.write_text('-----BEGIN PUBLIC KEY-----\n' + public + '\n-----END PUBLIC KEY-----\n')
        sig.write_bytes(signature)
        result = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(pub), '-signature', str(sig)],
                                input=domain.encode() + b'\n' + raw, capture_output=True)
        if result.returncode != 0:
            raise ValueError('签名校验失败')
    return protocol.strict_json(raw)


def validate_sources() -> None:
    # Validate using the APK's dependency-free sources, which have no .env file.
    subprocess.run([os.sys.executable, str(ROOT / 'scripts/stage-android-python.py')], check=True, capture_output=True)
    staged = ROOT / 'frontend/android/app/build/generated/python'
    code = (
        'import json,sys,tempfile\n'
        'from pathlib import Path\n'
        'from app.core.runtime import configure_embedded\n'
        'with tempfile.TemporaryDirectory() as directory:\n'
        ' configure_embedded(directory, lambda _: None)\n'
        ' from app.services.story_catalog import parse_package, _apply_builtin_artwork\n'
        ' source=Path(sys.argv[1])\n'
        ' for name in json.loads((source/"manifest.json").read_text())["packages"]:\n'
        '  package=json.loads((source/name).read_text())\n'
        '  archive=parse_package(package,"builtin")\n'
        '  _apply_builtin_artwork(archive,package.get("artwork",{}))\n'
    )
    result = subprocess.run([os.sys.executable, '-S', '-c', code, str(ROOT / 'backend/app/content/stories')],
        env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(staged), 'PYTHONIOENCODING': 'utf-8'},
        capture_output=True)
    if result.returncode:
        raise ValueError('本地正文结构与证据可达性校验失败；未生成发布目录')


def write_catalog(payload: dict, output: Path, key: Path, key_id: str, config: dict) -> None:
    """Preserve issued bytes and reject overwriting a newer local directory."""
    pointer = output / 'catalog.json'
    if pointer.exists():
        previous = verify_envelope(protocol.strict_json(pointer.read_bytes()), 'MMG-CATALOG-V1', config['keys'])
        if previous['catalog_revision'] > payload['catalog_revision']:
            raise ValueError('拒绝目录修订回退')
    path = output / f'catalog-r{payload["catalog_revision"]}.json'
    if path.exists():
        existing = verify_envelope(protocol.strict_json(path.read_bytes()), 'MMG-CATALOG-V1', config['keys'])
        existing.pop('issued_at', None)
        comparable = dict(payload)
        comparable.pop('issued_at', None)
        if existing != comparable:
            raise ValueError('同一目录修订内容变化，请提高 revision')
    else:
        path.write_text(json.dumps(envelope(payload, 'MMG-CATALOG-V1', key, key_id), indent=2) + '\n')
    pointer.write_bytes(path.read_bytes())


def make_bundle(source: Path, out: Path, commit: str, key: Path | None, key_id: str) -> tuple[dict, dict]:
    raw = source.read_bytes()
    package = protocol.strict_json(raw)
    sid = package['archive']['id']
    version = package['metadata']['version']
    if not re.fullmatch(r'[a-f0-9-]{36}', sid) or type(version) is not int or version < 1:
        raise ValueError('剧本 ID 或内容版本无效')
    files = {'package.json': raw, 'LICENSE': (ROOT / 'LICENSE').read_bytes(),
             'SOURCE.txt': (f'Publisher: {PUBLISHER}\nAuthor: {package["metadata"]["author"]}\n'
                            f'Source commit: {commit}\n'
                            f'Source: https://github.com/{PUBLISHER}/tree/{commit}\n').encode()}
    source_files = [source, ROOT / 'LICENSE']
    images = {}
    for name in sorted(protocol.artwork_files(package)):
        path = ROOT / 'backend/app/content/images' / sid / name
        files[f'images/{name}'] = images[name] = path.read_bytes()
        source_files.append(path)
    if len(raw) > 2 * 1024 * 1024 or len(files) > 63 or sum(map(len, files.values())) > 40 * 1024 * 1024:
        raise ValueError('内容包超过限制')
    manifest = {'kind': 'murder-mystery-story-bundle', 'bundle_format': 1, 'publisher': PUBLISHER,
        'story_id': sid, 'content_version': version, 'min_engine_version': 1, 'package_format': 1,
        'source_commit': commit, 'files': [{'path': name, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())]}
    info = {name: package['metadata'][name] for name in ('summary', 'difficulty', 'estimated_minutes', 'author', 'license')}
    info.update(story_id=sid, content_version=version, title=package['archive']['title'],
                num_characters=len(package['archive']['characters']), min_engine_version=1,
                package_format=1, bundle_format=1, status='active',
                release_notes=package['metadata'].get('release_notes', '原创剧本内容包。'))
    report = {'story_id': sid, 'content_version': version, 'signed': key is not None,
              'content_fingerprint': protocol.content_fingerprint(raw, images), 'files': manifest['files']}
    if key is None:
        return info, report
    for path in source_files:
        assert_source(path, commit)
    filename = f'{sid}-v{version}.mmstory'
    destination = out / filename
    # Reuse already signed artifacts: a source-only commit change doesn't
    # justify a new ZIP/signature for an unchanged content version.
    if destination.exists():
        with ZipFile(destination) as archive:
            old = verify_envelope(protocol.strict_json(archive.read('bundle.json')), 'MMG-BUNDLE-V1',
                                  json.loads((ROOT / 'content/config.json').read_text())['keys'])
            old_commit = old['source_commit']
            if not re.fullmatch(r'[a-f0-9]{40}', old_commit) or old['story_id'] != sid or old['content_version'] != version:
                raise ValueError('缓存内容版本或来源无效')
            if set(archive.namelist()) != set(files) | {'bundle.json'}:
                raise ValueError('同版本文件清单变化，请提高内容版本')
            for row in old['files']:
                actual = archive.read(row['path'])
                if len(actual) != row['bytes'] or hashlib.sha256(actual).hexdigest() != row['sha256']:
                    raise ValueError('缓存内容包损坏')
            for name, data in files.items():
                if name != 'SOURCE.txt' and archive.read(name) != data:
                    raise ValueError('同版本内容变化，请提高 metadata.version')
            for path in source_files:
                assert_source(path, old_commit)
        report.update(reused=True, source_commit=old_commit)
    else:
        files['bundle.json'] = json.dumps(envelope(manifest, 'MMG-BUNDLE-V1', key, key_id), separators=(',', ':')).encode()
        with tempfile.NamedTemporaryFile(dir=out, suffix='.tmp', delete=False) as temporary:
            staged = Path(temporary.name)
        try:
            with ZipFile(staged, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
                for name, data in sorted(files.items()):
                    entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    entry.compress_type = ZIP_DEFLATED
                    entry.external_attr = 0o100644 << 16
                    archive.writestr(entry, data)
            if staged.stat().st_size > 20 * 1024 * 1024:
                raise ValueError('压缩包不能超过 20 MiB')
            staged.rename(destination)
        finally:
            staged.unlink(missing_ok=True)
        report.update(reused=False, source_commit=commit)
    info.update(bytes=destination.stat().st_size, sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    report.update(filename=filename, bytes=info['bytes'], sha256=info['sha256'])
    return info, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/story-content')
    parser.add_argument('--revision', type=int, default=1)
    parser.add_argument('--source-commit', default='WORKTREE-UNSIGNED')
    parser.add_argument('--signing-key', type=Path)
    parser.add_argument('--key-id', default='official-content-2026-01')
    parser.add_argument('--previous-catalog', type=Path, help='Previously signed directory; required after revision 1')
    args = parser.parse_args()
    if args.revision < 1:
        parser.error('revision must be positive')
    if args.signing_key:
        if not re.fullmatch(r'[a-f0-9]{40}', args.source_commit) or set(args.source_commit) == {'0'}:
            parser.error('signed output requires a fixed non-placeholder source commit')
        if args.signing_key.resolve().is_relative_to(ROOT):
            parser.error('private signing key must live outside the repository')
        config = json.loads((ROOT / 'content/config.json').read_text())
        public = subprocess.run(['openssl', 'pkey', '-in', str(args.signing_key), '-pubout', '-outform', 'DER'],
                                capture_output=True, check=True).stdout
        if base64.b64encode(public).decode() != config['keys'].get(args.key_id):
            parser.error('signing key does not match the trusted public key')
    previous = {}
    if args.signing_key and args.revision > 1 and not args.previous_catalog:
        parser.error('later releases require --previous-catalog and the unchanged signed artifacts')
    if args.previous_catalog:
        config = json.loads((ROOT / 'content/config.json').read_text())
        old = verify_envelope(protocol.strict_json(args.previous_catalog.read_bytes()), 'MMG-CATALOG-V1', config['keys'])
        if old['publisher'] != PUBLISHER or old['catalog_revision'] >= args.revision:
            parser.error('previous directory publisher/revision mismatch')
        previous = {entry['story_id']: entry for entry in old['entries']}
    validate_sources()
    args.output.mkdir(parents=True, exist_ok=True)
    entries, reports = [], []
    manifest = json.loads((ROOT / 'backend/app/content/stories/manifest.json').read_text())
    for name in manifest['packages']:
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('Invalid content filename')
        source = ROOT / 'backend/app/content/stories' / name
        package = protocol.strict_json(source.read_bytes())
        old = previous.get(package['archive']['id'])
        if old:
            version = package['metadata']['version']
            if version < old['content_version']:
                raise ValueError('拒绝内容版本回退')
            cached = args.output / f'{old["story_id"]}-v{old["content_version"]}.mmstory'
            if args.signing_key and version == old['content_version'] and not cached.exists():
                raise ValueError(f'缺少已发布产物，请按原字节放入输出目录：{cached.name}')
        entry, report = make_bundle(source, args.output,
                                   args.source_commit, args.signing_key, args.key_id)
        if args.signing_key:
            if old and entry['content_version'] == old['content_version']:
                if entry['sha256'] != old['sha256'] or entry['bytes'] != old['bytes']:
                    raise ValueError('已发布版本的 ZIP 字节变化')
                entry['download_urls'] = old['download_urls']
            else:
                entry['download_urls'] = [f'https://github.com/{PUBLISHER}/releases/download/content-r{args.revision}/{report["filename"]}']
        entries.append(entry)
        reports.append(report)
    if len({entry['story_id'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate story ID')
    (args.output / 'report.json').write_text(json.dumps({'dry_run': args.signing_key is None,
        'catalog_revision': args.revision, 'source_commit': args.source_commit, 'stories': reports}, ensure_ascii=False, indent=2) + '\n')
    if args.signing_key:
        payload = {'kind': 'murder-mystery-catalog', 'catalog_format': 1, 'catalog_revision': args.revision,
            'publisher': PUBLISHER, 'channel': 'stable', 'issued_at': datetime.now(timezone.utc).isoformat(), 'entries': entries}
        write_catalog(payload, args.output, args.signing_key, args.key_id, config)
    print(json.dumps({'dry_run': args.signing_key is None, 'stories': len(reports),
                      'output': str(args.output), 'uploaded': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
