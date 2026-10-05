"""Stage only audited Python source; never bundle backend configuration/data."""
from pathlib import Path
import json
import importlib.util
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'frontend/android/app/build/generated/python'
SOURCE_FILES = [
    '__init__.py', 'domain/__init__.py', 'domain/models.py',
    'domain/context.py', 'domain/game_manager.py', 'core/__init__.py',
    'core/phases.py', 'core/config.py', 'core/prompts.py', 'core/content_protocol.py',
    'core/errors.py', 'core/runtime.py', 'core/logging.py', 'core/llm_trace.py',
    'core/prompt_cache.py', 'core/roleplay_protocol.py',
    'agents/__init__.py', 'agents/roleplay_character.py',
    'services/__init__.py', 'services/context_service.py',
    'services/session_service.py', 'services/story_service.py', 'services/image_service.py',
    'services/story_catalog.py',
    'services/story_content_service.py',
]

def stage():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    for name in SOURCE_FILES:
        dest = TARGET / 'app' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'backend/app' / name, dest)
    for source in (ROOT / 'mobile_engine').glob('*.py'):
        shutil.copyfile(source, TARGET / source.name)
    # Only the reviewed bundled case, never a user's current sessions or .env.
    assets = ROOT / 'frontend/android/app/build/generated/game-assets/stories'
    assets.mkdir(parents=True, exist_ok=True)
    catalog = assets / 'catalog'
    if catalog.exists():
        shutil.rmtree(catalog)
    catalog.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('content_protocol', ROOT / 'backend/app/core/content_protocol.py')
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    content = ROOT / 'backend/app/content'
    base = json.loads((content / 'android-base.json').read_text())
    manifest = {'format_version': 1, 'packages': base['packages'], 'content_fingerprints': {}}
    for filename in base['packages']:
        if Path(filename).name != filename or not filename.endswith('.json'):
            raise ValueError('Invalid base story filename')
        raw = (content / 'stories' / filename).read_bytes()
        package = json.loads(raw)
        images = {name: (content / 'images' / package['archive']['id'] / name).read_bytes()
                  for name in protocol.artwork_files(package)}
        manifest['content_fingerprints'][package['archive']['id']] = protocol.content_fingerprint(raw, images)
        (catalog / filename).write_bytes(raw)
    (catalog / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    shutil.copyfile(ROOT / 'content/config.json', assets.parent / 'story-library-config.json')
    name = 'bf5d01d5-94b0-4b9b-a207-d95d4433a91e.json'
    shutil.copyfile(ROOT / 'backend/stories' / name, assets / name)
    print(f'Staged {len(SOURCE_FILES)} shared source files and {len(base["packages"])} base cases (no env or sessions).')

if __name__ == '__main__':
    stage()
