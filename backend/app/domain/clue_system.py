# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Clue system - manages clue allocation and visibility."""

from typing import Optional
from app.domain.models import ClueData, ClueStatus, ClueBoard, ClueBoardEntry


class ClueSystem:
    """Manages clues in the murder mystery game."""

    def __init__(self, clues: list[ClueData]):
        """Initialize the clue system.

        Args:
            clues: All clues in the game.
        """
        self._clues = {c.id: c for c in clues}

    def get_clue(self, clue_id: str) -> Optional[ClueData]:
        """Get a clue by ID.

        Args:
            clue_id: The clue ID.

        Returns:
            The clue or None if not found.
        """
        return self._clues.get(clue_id)

    def get_all_clues(self) -> list[ClueData]:
        """Get all clues.

        Returns:
            List of all clues.
        """
        return list(self._clues.values())

    def reveal_clue(self, clue_id: str) -> bool:
        """Reveal a clue to all players.

        Args:
            clue_id: The clue ID to reveal.

        Returns:
            True if the clue was found and revealed.
        """
        clue = self._clues.get(clue_id)
        if not clue:
            return False
        clue.reveal_to_all = True
        return True

    def hide_clue(self, clue_id: str) -> bool:
        """Hide a clue from all players.

        Args:
            clue_id: The clue ID to hide.

        Returns:
            True if the clue was found and hidden.
        """
        clue = self._clues.get(clue_id)
        if not clue:
            return False
        clue.reveal_to_all = False
        return True

    def is_clue_available(
        self,
        clue_id: str,
        player_known_clues: list[str],
    ) -> bool:
        """Check if a clue is available for a player to obtain.

        A clue is available if:
        1. The player doesn't already have it
        2. Either it has no required clue, or the player has the required clue

        Args:
            clue_id: The clue ID to check.
            player_known_clues: List of clue IDs the player already knows.

        Returns:
            True if the clue is available.
        """
        clue = self._clues.get(clue_id)
        if not clue:
            return False

        if clue_id in player_known_clues:
            return False

        if clue.required_clue_id:
            return clue.required_clue_id in player_known_clues

        return True

    def get_available_clues(
        self,
        player_known_clues: list[str],
        holder_id: Optional[str] = None,
    ) -> list[ClueData]:
        """Get all clues available for a player to obtain.

        Args:
            player_known_clues: List of clue IDs the player already knows.
            holder_id: Optional holder ID to filter by.

        Returns:
            List of available clues.
        """
        available = []
        for clue in self._clues.values():
            if clue.id in player_known_clues:
                continue
            if holder_id and clue.holder_id != holder_id:
                continue
            if clue.required_clue_id and clue.required_clue_id not in player_known_clues:
                continue
            available.append(clue)
        return available

    def get_clues_by_holder(self, holder_id: str) -> list[ClueData]:
        """Get all clues held by a specific character.

        Args:
            holder_id: The character's ID.

        Returns:
            List of clues held by the character.
        """
        return [
            clue for clue in self._clues.values()
            if clue.holder_id == holder_id
        ]

    def get_clues_by_type(self, clue_type: str) -> list[ClueData]:
        """Get all clues of a specific type.

        Args:
            clue_type: The clue type (physical, testimony, document).

        Returns:
            List of clues of the specified type.
        """
        return [
            clue for clue in self._clues.values()
            if clue.type == clue_type
        ]

    def get_revealed_clues(self) -> list[ClueData]:
        """Get all revealed clues.

        Returns:
            List of revealed clues.
        """
        return [
            clue for clue in self._clues.values()
            if clue.reveal_to_all
        ]

    def get_hidden_clues(self) -> list[ClueData]:
        """Get all hidden clues.

        Returns:
            List of hidden clues.
        """
        return [
            clue for clue in self._clues.values()
            if not clue.reveal_to_all
        ]
