#!/usr/bin/env python3
"""Offline story preflight and non-destructive artwork encoding; no model calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types


SIZES = {"cover": (960, 640), "portrait": (640, 960)}


def pure_contract(repo: Path) -> tuple[types.ModuleType, types.ModuleType]:
    """Import pure sources without eager package initializers reading .env/SDKs.

    This standalone CLI briefly substitutes namespace packages, restoring any
    existing app modules afterwards. It does not change the game's imports.
    """
    previous = {name: module for name, module in sys.modules.copy().items()
                if name == "app" or name.startswith("app.")}
    for name in previous:
        del sys.modules[name]
    try:
        for name in ("app", "app.core", "app.domain", "app.services"):
            module = types.ModuleType(name)
            module.__path__ = [str(repo / "backend" / name.replace(".", "/"))]
            module.__package__ = name
            sys.modules[name] = module
        protocol = importlib.import_module("app.core.content_protocol")
        catalog = importlib.import_module("app.services.story_catalog")
        return protocol, catalog
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(previous)


def pillow_image() -> types.ModuleType:
    """Load the optional local decoder without installing any dependency."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("图片检查/编码需要 Pillow，请使用已安装 Pillow 的 Python") from exc
    return Image


def image_info(path: Path) -> dict:
    """Fully decode a bounded WebP and report its public artifact properties."""
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError(f"图片超过8MiB：{path.name}")
    image_class = pillow_image()
    with image_class.open(path) as image:
        if image.format != "WEBP" or image.width * image.height > 16_000_000:
            raise ValueError(f"图片不是有效的受限WebP：{path.name}")
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError(f"配图应为静态图片：{path.name}")
        image.load()
        width, height = image.size
    raw = path.read_bytes()
    return {"file": path.name, "width": width, "height": height,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check_stories(repo: Path, package_path: Path | None = None, draft: bool = False) -> dict:
    """Reuse the game's pure validators; never load settings, sessions or clients."""
    repo = repo.resolve()
    content = repo / "backend/app/content/stories"
    if not (content / "manifest.json").is_file():
        raise ValueError("请指定含官方剧本manifest的项目根目录")
    protocol, catalog = pure_contract(repo)
    artwork_files, strict_json = protocol.artwork_files, protocol.strict_json

    if package_path is not None:
        paths = [package_path.resolve()]
    else:
        manifest = strict_json((content / "manifest.json").read_bytes())
        names = manifest.get("packages")
        if (manifest.get("format_version") != 1 or not isinstance(names, list) or not names
                or any(not isinstance(n, str) or Path(n).name != n or not n.endswith(".json") for n in names)
                or len(names) != len(set(names))):
            raise ValueError("剧本manifest格式错误或文件名重复")
        paths = [content / name for name in names]

    reports = []
    story_ids = set()
    for path in paths:
        if path.stat().st_size > catalog.MAX_PACKAGE_BYTES:
            raise ValueError(f"剧本包超过2MiB：{path.name}")
        package = strict_json(path.read_bytes())
        archive = catalog.parse_package(package, "builtin")
        if archive.id in story_ids:
            raise ValueError("剧本UUID重复")
        story_ids.add(archive.id)
        # The engine normalizes these flags on read; catch authoring errors first.
        for character in package["archive"]["characters"]:
            expected = character["id"] == archive.case.true_killer
            if type(character.get("is_killer")) is not bool or character["is_killer"] != expected:
                raise ValueError(f"原稿凶手标记与true_killer不一致：{character['id']}")
            if not character.get("public_introduction", "").strip():
                raise ValueError(f"缺少公开介绍：{character['id']}")
        if any(c.get("reveal_to_all", False) is not False for c in package["archive"]["clues"]):
            raise ValueError("原稿不能携带某局已公开线索的进度")

        art = package.get("artwork", {})
        catalog._apply_builtin_artwork(archive, art)
        names = artwork_files(package)
        if art and (type(art.get("version")) is not int or art["version"] < 1):
            raise ValueError("artwork.version须为正整数")
        if not draft:
            role_ids = {c.id for c in archive.characters}
            portraits = art.get("portraits", {})
            if not art.get("cover") or set(portraits) != role_ids:
                raise ValueError("成品须有封面与每个角色的独立画像；文本稿用--draft检查")
            active_names = [art["cover"], *portraits.values()]
            if len(set(active_names)) != len(active_names):
                raise ValueError("封面和各角色画像不能共用同一文件")

        image_root = repo / "backend/app/content/images" / archive.id
        images = []
        for name in sorted(names):
            image_path = image_root / name
            if image_path.is_symlink() or not image_path.resolve().is_relative_to(image_root.resolve()):
                raise ValueError(f"图片路径不安全：{name}")
            if not image_path.resolve().is_relative_to(repo):
                raise ValueError(f"图片必须位于仓库内：{name}")
            images.append(image_info(image_path))
        reports.append({"file": path.name, "story_id": archive.id, "title": archive.title,
                        "version": package["metadata"]["version"],
                        "roles": len(archive.characters), "clues": len(archive.clues),
                        "images": len(images), "image_bytes": sum(i["bytes"] for i in images)})

    return {"validation": "local-structure-routes-artwork-v1", "draft": draft,
            "semantic_review": "not_performed", "real_model_playthrough": "not_performed",
            "stories": reports}


def encode_artwork(source: Path, destination: Path, kind: str) -> dict:
    """Resize/encode without cropping, overwriting, generating or editing subjects."""
    if destination.suffix != ".webp":
        raise ValueError("成品文件扩展名必须为.webp")
    if destination.exists() or destination.is_symlink():
        raise ValueError("目标已存在，请使用新的版本化文件名")
    size = SIZES[kind]
    image_class = pillow_image()
    with image_class.open(source) as image:
        if image.width * image.height > 16_000_000 or getattr(image, "n_frames", 1) != 1:
            raise ValueError("原图必须为不超过1600万像素的静态图片")
        ratio = image.width / image.height
        if abs(ratio / (size[0] / size[1]) - 1) > 0.01:
            raise ValueError("原图比例不匹配；先调整构图，工具不自动裁切")
        image.load()
        resized = image.convert("RGBA" if "A" in image.getbands() else "RGB").resize(
            size, image_class.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".webp", delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        resized.save(staged, format="WEBP", quality=85, method=6)
        report = image_info(staged)
        # Atomic exclusive publication: even a racing writer cannot be overwritten.
        os.link(staged, destination)
        report.update(file=str(destination), kind=kind)
        return report
    finally:
        staged.unlink(missing_ok=True)
        resized.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="离线检查指定草稿或manifest全部包")
    check.add_argument("--repo", type=Path, required=True)
    check.add_argument("--package", type=Path)
    check.add_argument("--draft", action="store_true", help="允许尚未添加配图；不跳过正文校验")
    encode = subcommands.add_parser("encode", help="等比例编码为项目WebP，不覆盖已有图")
    encode.add_argument("--input", type=Path, required=True)
    encode.add_argument("--output", type=Path, required=True)
    encode.add_argument("--kind", choices=tuple(SIZES), required=True)
    args = parser.parse_args()
    try:
        report = (check_stories(args.repo, args.package, args.draft) if args.command == "check"
                  else encode_artwork(args.input, args.output, args.kind))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"检查失败：{exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
