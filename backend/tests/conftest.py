# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Shared pytest fixtures for the murder mystery test suite."""

from __future__ import annotations

import pytest

from app.domain.models import (
    CaseData,
    ClueData,
    ScriptCharacter,
    StoryArchive,
)


def _char(
    id: str,
    name: str,
    is_killer: bool = False,
    clues: list[str] | None = None,
) -> ScriptCharacter:
    return ScriptCharacter(
        id=id,
        name=name,
        public_identity=f"{name}的公开身份",
        secret=f"{name}的秘密",
        is_killer=is_killer,
        clues=clues or [],
        alibi=f"{name}的不在场证明",
        dialogue_style="冷静",
        backstory=f"{name}的背景故事",
        relationship_with_victim=f"{name}与受害者的关系",
        motive="作案动机" if is_killer else "",
        appearance=f"{name}的外貌",
    )


def _clue(
    id: str,
    holder: str = "scene",
    type_: str = "physical",
    reveal: bool = False,
    required: str | None = None,
) -> ClueData:
    return ClueData(
        id=id,
        content=f"线索{id}的内容",
        type=type_,
        holder_id=holder,
        reveal_to_all=reveal,
        required_clue_id=required,
    )


@pytest.fixture
def sample_archive() -> StoryArchive:
    """Return a 4-character archive with char_1 as the killer and 6 clues.

    Layout:
        char_1 (killer) — holds clue_a
        char_2         — holds clue_b
        char_3         — holds clue_c
        char_4         — holds clue_d
        scene          — holds clue_scene (public) + clue_locked (gated)
    """
    chars = [
        _char("char_1", "Alice", is_killer=True, clues=["clue_a"]),
        _char("char_2", "Bob", clues=["clue_b"]),
        _char("char_3", "Carol", clues=["clue_c"]),
        _char("char_4", "Dave", clues=["clue_d"]),
    ]
    clues = [
        _clue("clue_a", holder="char_1", type_="physical"),
        _clue("clue_b", holder="char_2", type_="testimony"),
        _clue("clue_c", holder="char_3", type_="document"),
        _clue("clue_d", holder="char_4", type_="physical"),
        _clue("clue_scene", holder="scene", type_="document", reveal=True),
        _clue(
            "clue_locked",
            holder="char_1",
            type_="physical",
            required="clue_a",
        ),
    ]
    case = CaseData(
        title="测试案件",
        background="案件背景",
        victim="受害者",
        crime="受害者被害",
        true_killer="char_1",
        motive="动机",
    )
    return StoryArchive(
        id="story_test",
        created_at="2026-06-04 00:00:00",
        topic="测试主题",
        title="测试案件",
        case=case,
        characters=chars,
        clues=clues,
        story_content="完整真相",
    )
