# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Import stories from JSON files into the backend story format."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.domain.models import StoryArchive


def import_story(json_path: str) -> StoryArchive:
    """Import a story from a JSON file.

    Args:
        json_path: Path to the JSON story file.

    Returns:
        StoryArchive instance.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return StoryArchive.from_dict(data)


def main():
    """Main import function."""
    if len(sys.argv) < 2:
        print("Usage: python import_story.py <story_json_path>")
        print("Example: python import_story.py D:/Stata/Script_kill/stories/af787f07-dbb4-48a9-b4fd-6c1e02cbb116.json")
        sys.exit(1)

    json_path = sys.argv[1]

    if not os.path.exists(json_path):
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    print(f"Importing story from: {json_path}")

    archive = import_story(json_path)

    print(f"\nStory imported successfully!")
    print(f"  ID: {archive.id}")
    print(f"  Title: {archive.title}")
    print(f"  Topic: {archive.topic}")
    print(f"  Case: {archive.case.title}")
    print(f"  Characters: {len(archive.characters)}")
    print(f"  Clues: {len(archive.clues)}")
    print(f"  Created: {archive.created_at}")

    output_path = json_path.replace('.json', '_imported.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(archive.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {output_path}")

    return archive


if __name__ == "__main__":
    main()
