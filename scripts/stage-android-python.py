"""Stage only audited Python source; never bundle backend configuration/data."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'frontend/android/app/build/generated/python'
SOURCE_FILES = [
    '__init__.py', 'domain/__init__.py', 'domain/models.py',
    'domain/context.py', 'domain/game_manager.py', 'core/__init__.py',
    'core/phases.py', 'core/config.py', 'core/prompts.py',
    'core/errors.py', 'core/runtime.py', 'core/logging.py', 'core/llm_trace.py',
    'core/prompt_cache.py', 'core/roleplay_protocol.py',
    'agents/__init__.py', 'agents/roleplay_character.py',
    'services/__init__.py', 'services/context_service.py',
    'services/session_service.py', 'services/story_service.py', 'services/image_service.py',
    'services/story_catalog.py',
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
    shutil.copytree(ROOT / 'backend/app/content/stories', catalog)
    name = 'bf5d01d5-94b0-4b9b-a207-d95d4433a91e.json'
    shutil.copyfile(ROOT / 'backend/stories' / name, assets / name)
    print(f'Staged {len(SOURCE_FILES)} shared source files (no env or sessions).')

if __name__ == '__main__':
    stage()
