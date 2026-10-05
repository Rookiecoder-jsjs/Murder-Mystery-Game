"""Offline authoring guard checks using real story data and actual image decoding."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "story_skill_tools", ROOT / "skills/update-mystery-stories/scripts/story_tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class StorySkillToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        content = ROOT / "backend/app/content/stories"
        first = json.loads((content / "manifest.json").read_text())["packages"][0]
        self.package = json.loads((content / first).read_text())

    def save(self, package):
        path = self.directory / "draft.json"
        path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
        return path

    def test_existing_catalog_and_artwork_are_valid_but_not_semantic_review(self):
        real_read = Path.read_bytes
        real_open = Path.open
        def guarded_read(path):
            self.assertNotEqual(path.name, ".env", "preflight must not read project keys")
            return real_read(path)
        def guarded_open(path, *args, **kwargs):
            self.assertNotEqual(path.name, ".env", "preflight must not read project keys")
            return real_open(path, *args, **kwargs)
        with patch.object(Path, "read_bytes", guarded_read), patch.object(Path, "open", guarded_open):
            report = tools.check_stories(ROOT)
        manifest = json.loads((ROOT / "backend/app/content/stories/manifest.json").read_text())
        self.assertEqual(len(report["stories"]), len(manifest["packages"]))
        self.assertEqual(report["semantic_review"], "not_performed")
        for story in report["stories"]:
            self.assertGreaterEqual(story["images"], story["roles"] + 1)

    def test_draft_without_art_does_not_pass_finished_check(self):
        package = copy.deepcopy(self.package)
        package.pop("artwork", None)
        path = self.save(package)
        self.assertTrue(tools.check_stories(ROOT, path, draft=True)["draft"])
        with self.assertRaisesRegex(ValueError, "封面"):
            tools.check_stories(ROOT, path)

    def test_normalization_cannot_hide_wrong_killer_or_runtime_progress(self):
        package = copy.deepcopy(self.package)
        package["archive"]["characters"][0]["is_killer"] = not package["archive"]["characters"][0]["is_killer"]
        with self.assertRaisesRegex(ValueError, "凶手标记"):
            tools.check_stories(ROOT, self.save(package), draft=True)
        package = copy.deepcopy(self.package)
        package["archive"]["clues"][0]["reveal_to_all"] = True
        with self.assertRaisesRegex(ValueError, "进度"):
            tools.check_stories(ROOT, self.save(package), draft=True)

    def test_nonempty_webp_header_is_not_enough_to_pass_decode(self):
        path = self.directory / "broken.webp"
        path.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
        with self.assertRaises((OSError, ValueError)):
            tools.image_info(path)

    def test_encode_is_real_webp_and_preserves_existing_destination(self):
        source = ROOT / "backend/app/content/images" / self.package["archive"]["id"] / self.package["artwork"]["cover"]
        destination = self.directory / "cover-v9.webp"
        report = tools.encode_artwork(source, destination, "cover")
        self.assertEqual((report["width"], report["height"]), (960, 640))
        original = destination.read_bytes()
        with self.assertRaisesRegex(ValueError, "已存在"):
            tools.encode_artwork(source, destination, "cover")
        self.assertEqual(destination.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "比例"):
            tools.encode_artwork(source, self.directory / "portrait-v9.webp", "portrait")
        self.assertFalse((self.directory / "portrait-v9.webp").exists())


if __name__ == "__main__":
    unittest.main()
