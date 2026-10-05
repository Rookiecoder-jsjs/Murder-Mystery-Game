"""Real OpenSSL and Git checks for immutable local publishing, never uploads."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'package-story-content.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.key = self.directory / 'test.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', str(self.key)], check=True, capture_output=True)
        public = subprocess.run(['openssl', 'pkey', '-in', str(self.key), '-pubout', '-outform', 'DER'], check=True, capture_output=True).stdout
        self.config = {'keys': {'test': base64.b64encode(public).decode()}}

    def test_signature_checks_raw_bytes_domain_and_key(self):
        payload = {'catalog_revision': 1, 'title': '原创测试'}
        wrapper = publisher.envelope(payload, 'MMG-CATALOG-V1', self.key, 'test')
        self.assertEqual(publisher.verify_envelope(wrapper, 'MMG-CATALOG-V1', self.config['keys']), payload)
        for domain, keys in [('MMG-BUNDLE-V1', self.config['keys']), ('MMG-CATALOG-V1', {})]:
            with self.assertRaises(ValueError):
                publisher.verify_envelope(wrapper, domain, keys)
        wrapper['payload_b64'] = base64.b64encode(b'{"catalog_revision":2}').decode()
        with self.assertRaises(ValueError):
            publisher.verify_envelope(wrapper, 'MMG-CATALOG-V1', self.config['keys'])

    def test_catalog_reuse_conflict_and_rollback(self):
        payload = {'catalog_revision': 1, 'issued_at': '2026-10-05T00:00:00Z', 'entries': []}
        publisher.write_catalog(payload, self.directory, self.key, 'test', self.config)
        first = (self.directory / 'catalog.json').read_bytes()
        publisher.write_catalog({**payload, 'issued_at': '2026-10-06T00:00:00Z'}, self.directory, self.key, 'test', self.config)
        self.assertEqual((self.directory / 'catalog.json').read_bytes(), first)
        with self.assertRaises(ValueError):
            publisher.write_catalog({**payload, 'entries': [{'changed': True}]}, self.directory, self.key, 'test', self.config)
        publisher.write_catalog({**payload, 'catalog_revision': 2}, self.directory, self.key, 'test', self.config)
        second = (self.directory / 'catalog.json').read_bytes()
        with self.assertRaises(ValueError):
            publisher.write_catalog(payload, self.directory, self.key, 'test', self.config)
        self.assertEqual((self.directory / 'catalog.json').read_bytes(), second)

    def test_bundle_reuses_published_bytes_and_rejects_same_version_edits(self):
        root = self.directory / 'repo'
        root.mkdir()
        previous_root = publisher.ROOT
        publisher.ROOT = root
        self.addCleanup(setattr, publisher, 'ROOT', previous_root)
        source = root / 'case.json'
        package = {'format_version': 1, 'metadata': {'version': 1, 'summary': '测试', 'difficulty': '入门', 'estimated_minutes': 30, 'author': '测试', 'license': 'AGPL-3.0-only'},
                   'archive': {'id': 'ad60c7e0-1f56-4fc3-bcaa-705910d03304', 'title': '测试案卷', 'characters': [{}, {}, {}]}}
        source.write_text(json.dumps(package, ensure_ascii=False))
        (root / 'LICENSE').write_text('Test license')
        (root / 'content').mkdir()
        (root / 'content/config.json').write_text(json.dumps(self.config))
        def git(*args):
            return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout.decode().strip()
        git('init', '-q')
        git('add', '.')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'test')
        commit = git('rev-parse', 'HEAD')
        output = root / 'output'
        output.mkdir()
        info, report = publisher.make_bundle(source, output, commit, self.key, 'test')
        self.assertFalse(report['reused'])
        original = (output / report['filename']).read_bytes()
        (root / 'unrelated.txt').write_text('source-only change')
        git('add', 'unrelated.txt')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'unrelated')
        latest = git('rev-parse', 'HEAD')
        reused, report = publisher.make_bundle(source, output, latest, self.key, 'test')
        self.assertTrue(report['reused'])
        self.assertEqual(info, reused)
        self.assertEqual((output / report['filename']).read_bytes(), original)
        source.write_bytes(source.read_bytes() + b' ')
        with self.assertRaises(Exception):
            publisher.make_bundle(source, output, latest, self.key, 'test')
        git('add', 'case.json')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'same version edit')
        with self.assertRaisesRegex(ValueError, '同版本内容变化'):
            publisher.make_bundle(source, output, git('rev-parse', 'HEAD'), self.key, 'test')


if __name__ == '__main__':
    unittest.main()
