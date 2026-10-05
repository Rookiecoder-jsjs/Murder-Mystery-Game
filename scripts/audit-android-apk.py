"""Audit an APK and nested Chaquopy archives without printing secret values."""
import argparse
import base64
import hashlib
import io
import importlib.util
import json
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

ROOT = Path(__file__).resolve().parents[1]
KEY_PATTERN = re.compile(rb"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})")
PRIVATE_KEY_PATTERN = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")


def local_secret_bytes(env_path: Path) -> set[bytes]:
    """Read only key/token settings for in-memory comparison; never log them."""
    secrets = set()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*(?:export\s+)?([A-Z0-9_]*(?:API_KEY|TOKEN))\s*=\s*(.*?)\s*$", line)
            if not match:
                continue
            value = match[2].split(" #", 1)[0].strip().strip("\"'")
            if len(value) < 12 or re.search(r"placeholder|your[_-]|xxxx|填|替换", value, re.I):
                continue
            encoded = value.encode()
            secrets.update((encoded, value.encode("utf-16le"), base64.b64encode(encoded)))
    return secrets


def audit(apk: Path, secrets: set[bytes]) -> dict:
    """Reject credentials/user data and verify bundled catalog/artwork bytes."""
    scanned = 0
    errors = []

    def scan(data: bytes, name: str, depth: int = 0):
        nonlocal scanned
        scanned += 1
        parts = Path(name.split("!/")[-1]).parts
        if any(part.startswith(".env") or part in {"sessions", "logs", "shared_prefs"}
               for part in parts) or name.endswith((".keystore", ".jks", ".db", ".sqlite", ".sqlite3")):
            errors.append(f"禁止打包的配置或用户数据：{name}")
        if KEY_PATTERN.search(data) or PRIVATE_KEY_PATTERN.search(data) or any(secret in data for secret in secrets):
            errors.append(f"发现凭据内容：{name}（值已隐藏）")
        stream = io.BytesIO(data)
        if is_zipfile(stream):
            if depth >= 4:
                raise ValueError("嵌套归档过深，无法完成检查")
            try:
                nested = ZipFile(stream)
            except BadZipFile:
                # DEX code for the ZIP verifier contains an EOCD byte pattern.
                # is_zipfile checks only that pattern, not central-dir offsets.
                # Its raw bytes were still scanned above. Actual archive assets
                # must open successfully before the APK can pass this audit.
                if data.startswith(b'PK\x03\x04') or name.lower().endswith(('.zip', '.imy', '.apk', '.jar', '.mmstory')):
                    raise ValueError(f'无法检查损坏的归档：{name}')
                return
            with nested:
                for entry in nested.infolist():
                    if not entry.is_dir():
                        scan(nested.read(entry), f"{name}!/{entry.filename}", depth + 1)

    with ZipFile(apk) as archive:
        for entry in archive.infolist():
            if not entry.is_dir():
                scan(archive.read(entry), entry.filename)
        config = json.loads(archive.read("assets/capacitor.config.json"))
        if config.get("server", {}).get("url"):
            errors.append("APK 配置依赖远程页面")
        source = ROOT / "backend/app/content"
        base = json.loads((source / "android-base.json").read_text())
        spec = importlib.util.spec_from_file_location("content_protocol", ROOT / "backend/app/core/content_protocol.py")
        protocol = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(protocol)
        manifest = {"format_version": 1, "packages": base["packages"], "content_fingerprints": {}}
        for filename in base["packages"]:
            raw = (source / "stories" / filename).read_bytes()
            package = json.loads(raw)
            images = {name: (source / "images" / package["archive"]["id"] / name).read_bytes()
                      for name in protocol.artwork_files(package)}
            manifest["content_fingerprints"][package["archive"]["id"]] = protocol.content_fingerprint(raw, images)
        if archive.read("assets/story-library-config.json") != (ROOT / "content/config.json").read_bytes():
            errors.append("内容目录或受信公钥与源码不同")
        catalog_names = {"manifest.json", *manifest["packages"]}
        actual_names = {name.removeprefix("assets/stories/catalog/")
                        for name in archive.namelist() if name.startswith("assets/stories/catalog/")
                        and not name.endswith("/")}
        if actual_names != catalog_names:
            errors.append("APK 剧本目录与发布清单不一致")
        image_count = 0
        for filename in sorted(catalog_names):
            expected = ((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
                        if filename == "manifest.json" else (source / "stories" / filename).read_bytes())
            if archive.read(f"assets/stories/catalog/{filename}") != expected:
                errors.append(f"剧本包与源码不同：{filename}")
            if filename == "manifest.json":
                continue
            package = json.loads(expected)
            artwork = package.get("artwork", {})
            for image in {artwork.get("cover"), *artwork.get("portraits", {}).values(),
                          *artwork.get("retained_files", [])} - {None}:
                story_id = package["archive"]["id"]
                if archive.read(f"assets/public/assets/story-library/{story_id}/{image}") != (source / "images" / story_id / image).read_bytes():
                    errors.append(f"配图与源码不同：{story_id}/{image}")
                image_count += 1
    if errors:
        raise ValueError("\n".join(errors))
    return {"apk": apk.name, "bytes": apk.stat().st_size,
            "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "scanned_entries": scanned, "builtin_stories": len(manifest["packages"]),
            "artwork_files": image_count, "credential_scan": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--secret-env", type=Path, default=ROOT / "backend/.env")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.apk, local_secret_bytes(args.secret_env)), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"APK 检查失败：{error}\n")
