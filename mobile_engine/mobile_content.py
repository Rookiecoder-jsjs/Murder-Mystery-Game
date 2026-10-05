"""Fixed native installer ports; never dispatch caller-selected Python methods."""
import json
from pathlib import Path


def configure(directory: str, bundled: str) -> None:
    from app.core.runtime import configure_embedded, is_embedded
    if not is_embedded():
        # Content checks never construct or invoke a model client.
        configure_embedded(str(Path(directory).parent / 'game'), lambda _: None)
    from app.services import story_catalog, story_content_service
    story_catalog.CONTENT_DIR = Path(bundled) / 'catalog'
    story_content_service.configure(directory)


def validate(directory: str, digest: str) -> str:
    from app.services.story_content_service import validate_package
    return json.dumps(validate_package(directory, digest), ensure_ascii=False)


def activate(story_id: str, version: int, digest: str, personal: str) -> str:
    from app.services.story_content_service import activate as commit
    return json.dumps(commit(story_id, version, digest, personal), ensure_ascii=False)


def remove(story_id: str) -> None:
    from app.services.story_content_service import deactivate
    deactivate(story_id)


def state() -> str:
    from app.services.story_content_service import read_registry, official_stories
    from app.services.story_catalog import story_info
    registry = read_registry()
    return json.dumps({'library_revision': registry['library_revision'],
                       'stories': [story_info(a) for a in official_stories()]}, ensure_ascii=False)


def is_installed(story_id: str, version: int, digest: str) -> bool:
    from app.services.story_content_service import is_installed as check
    return check(story_id, version, digest)
