# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Unit tests for ClueSystem — pure logic over ClueData lists."""

from __future__ import annotations

import pytest

from app.domain.clue_system import ClueSystem
from app.domain.models import ClueData


def _clue(
    id: str,
    holder: str = "scene",
    type_: str = "physical",
    reveal: bool = False,
    required: str | None = None,
) -> ClueData:
    return ClueData(
        id=id,
        content=f"内容{id}",
        type=type_,
        holder_id=holder,
        reveal_to_all=reveal,
        required_clue_id=required,
    )


@pytest.fixture
def system() -> ClueSystem:
    clues = [
        _clue("c1", holder="char_1", type_="physical"),
        _clue("c2", holder="char_2", type_="testimony"),
        _clue("c3", holder="char_1", type_="document"),
        _clue("c4", holder="scene", type_="physical", reveal=True),
        _clue("c5", holder="char_2", type_="physical", required="c2"),
    ]
    return ClueSystem(clues)


class TestLookup:
    def test_get_clue_existing(self, system):
        assert system.get_clue("c1").holder_id == "char_1"

    def test_get_clue_missing(self, system):
        assert system.get_clue("missing") is None

    def test_get_all_clues(self, system):
        ids = {c.id for c in system.get_all_clues()}
        assert ids == {"c1", "c2", "c3", "c4", "c5"}


class TestReveal:
    def test_reveal_clue_marks_public(self, system):
        assert system.reveal_clue("c1") is True
        assert system.get_clue("c1").reveal_to_all is True

    def test_reveal_missing_returns_false(self, system):
        assert system.reveal_clue("missing") is False

    def test_hide_clue_unmarks(self, system):
        system.reveal_clue("c1")
        assert system.hide_clue("c1") is True
        assert system.get_clue("c1").reveal_to_all is False

    def test_hide_missing_returns_false(self, system):
        assert system.hide_clue("missing") is False


class TestAvailability:
    def test_unowned_and_no_prereq_is_available(self, system):
        assert system.is_clue_available("c1", player_known_clues=[]) is True

    def test_owned_is_not_available(self, system):
        assert system.is_clue_available("c1", player_known_clues=["c1"]) is False

    def test_prereq_not_held_is_not_available(self, system):
        assert system.is_clue_available("c5", player_known_clues=[]) is False

    def test_prereq_held_is_available(self, system):
        assert system.is_clue_available("c5", player_known_clues=["c2"]) is True

    def test_missing_clue_is_not_available(self, system):
        assert system.is_clue_available("missing", []) is False

    def test_get_available_excludes_owned(self, system):
        avail = system.get_available_clues(["c1", "c2"])
        ids = {c.id for c in avail}
        assert "c1" not in ids and "c2" not in ids
        assert {"c3", "c4", "c5"} <= ids

    def test_get_available_filters_holder(self, system):
        avail = system.get_available_clues([], holder_id="char_1")
        ids = {c.id for c in avail}
        assert ids == {"c1", "c3"}
        assert "c2" not in ids and "c4" not in ids

    def test_get_available_excludes_gated(self, system):
        avail = system.get_available_clues([])
        ids = {c.id for c in avail}
        assert "c5" not in ids
        avail2 = system.get_available_clues(["c2"])
        ids2 = {c.id for c in avail2}
        assert "c5" in ids2


class TestFilters:
    def test_get_clues_by_holder(self, system):
        assert {c.id for c in system.get_clues_by_holder("char_1")} == {"c1", "c3"}
        assert {c.id for c in system.get_clues_by_holder("scene")} == {"c4"}

    def test_get_clues_by_type(self, system):
        assert {c.id for c in system.get_clues_by_type("physical")} == {
            "c1", "c4", "c5"
        }
        assert {c.id for c in system.get_clues_by_type("testimony")} == {"c2"}
        assert {c.id for c in system.get_clues_by_type("document")} == {"c3"}

    def test_get_revealed_and_hidden(self, system):
        revealed = {c.id for c in system.get_revealed_clues()}
        hidden = {c.id for c in system.get_hidden_clues()}
        assert revealed == {"c4"}
        assert hidden == {"c1", "c2", "c3", "c5"}
