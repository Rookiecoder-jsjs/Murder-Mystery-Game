"""Host adapters for the same Python sources on desktop and Android."""
from pathlib import Path
from typing import Callable, Any

_directory: Path | None = None
_model_factory: Callable[[str], Any] | None = None
_story_progress: Callable[[str, str], None] | None = None


def configure_embedded(directory: str, model_factory: Callable[[str], Any],
                       story_progress: Callable[[str, str], None] | None = None) -> None:
    """Call once before importing services; no credentials cross this port."""
    global _directory, _model_factory, _story_progress
    _directory = Path(directory)
    _directory.mkdir(parents=True, exist_ok=True)
    _model_factory = model_factory
    _story_progress = story_progress


def report_story_progress(stage: str, label: str) -> None:
    """Report real work boundaries; no prompts, credentials, or estimated percent."""
    if _story_progress is not None:
        _story_progress(stage, label)


def data_directory() -> Path:
    return _directory or Path(__file__).resolve().parents[2]


def is_embedded() -> bool:
    return _directory is not None


def model_client(kind: str, config):
    if _model_factory is not None:
        return _model_factory(kind)
    from openai import OpenAI
    return OpenAI(api_key=config.api_key, base_url=config.base_url)
