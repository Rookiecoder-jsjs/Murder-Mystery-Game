# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Base agent class for the murder mystery game."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.core.phases import GamePhase
from app.domain.models import ScriptCharacter, GameState


class BaseCharacterAgent(ABC):
    """Abstract base class for character agents in the murder mystery game."""

    def __init__(
        self,
        character: ScriptCharacter,
        model: Any,
    ):
        """Initialize the character agent.

        Args:
            character: The script character to represent.
            model: The model backend to use.
        """
        self.character = character
        self.model = model

    @property
    def character_id(self) -> str:
        """Get the character's ID."""
        return self.character.id

    @property
    def name(self) -> str:
        """Get the character's name."""
        return self.character.name

    @property
    def is_killer(self) -> bool:
        """Check if this character is the killer."""
        return self.character.is_killer

    @abstractmethod
    def respond(
        self,
        user_input: str,
        phase: GamePhase,
        game_state: GameState,
    ) -> str:
        """Generate a response to user input.

        Args:
            user_input: The user's input message.
            phase: The current game phase.
            game_state: The current game state.

        Returns:
            The agent's response message.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the agent's memory and state."""
