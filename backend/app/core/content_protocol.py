"""Pure content format helpers shared with offline publishing tools."""
import hashlib
import json
import re

_IMAGE = re.compile(r'[A-Za-z0-9_-]+\.webp')


def strict_json(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSON 字段重复')
            result[key] = value
        return result
    result = json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON 数值无效')))
    if not isinstance(result, dict):
        raise ValueError('内容文件必须为 JSON 对象')
    return result


def artwork_files(package: dict) -> set[str]:
    art = package.get('artwork', {})
    if not isinstance(art, dict) or not isinstance(art.get('portraits', {}), dict) or not isinstance(art.get('retained_files', []), list):
        raise ValueError('配图清单无效')
    names = [art.get('cover'), *art.get('portraits', {}).values(), *art.get('retained_files', [])]
    if any(not isinstance(name, str) or not _IMAGE.fullmatch(name) for name in names if name is not None):
        raise ValueError('配图文件名无效')
    return {name for name in names if name is not None}


def content_fingerprint(package_bytes: bytes, images: dict[str, bytes]) -> str:
    files = {'package.json': package_bytes, **{f'images/{name}': data for name, data in images.items()}}
    rows = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            for name, data in sorted(files.items())]
    raw = json.dumps({'fingerprint_format': 1, 'files': rows}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


