# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Murder mystery game workforce using CAMEL's Workforce."""

import asyncio
from typing import Any, Dict, List, Optional

from camel.societies.workforce import Workforce, SingleAgentWorker
from camel.agents import ChatAgent

from app.agents.m2_character import M2Character
from app.core.phases import GamePhase
from app.domain.models import StoryArchive, GameState, ScriptCharacter
from app.domain.game_manager import GameManager


class MurderMysteryWorkforce:
    """Workforce for managing the murder mystery game.

    This workforce manages all AI characters and coordinates their responses
    during different game phases.
    """

    def __init__(
        self,
        archive: StoryArchive,
        human_player_id: str,
        model_config: Dict[str, Any],
    ):
        """Initialize the murder mystery workforce.

        Args:
            archive: The story archive.
            human_player_id: The ID of the character controlled by the human.
            model_config: Configuration for the model.
        """
        self.archive = archive
        self.human_player_id = human_player_id
        self.model_config = model_config

        self._game_manager = GameManager(archive)
        self._characters: Dict[str, M2Character] = {}

    def initialize_characters(self, client: Any) -> None:
        """Initialize all AI character agents.

        Args:
            client: OpenAI client for M2-her.
        """
        for char in self.archive.characters:
            if char.id != self.human_player_id:
                agent = M2Character(
                    character=char,
                    client=client,
                )
                self._characters[char.id] = agent

    @property
    def game_manager(self) -> GameManager:
        """Get the game manager.

        Returns:
            The GameManager instance.
        """
        return self._game_manager

    @property
    def characters(self) -> Dict[str, M2Character]:
        """Get all character agents.

        Returns:
            Dictionary of character_id to M2Character.
        """
        return self._characters

    def get_character_agent(self, character_id: str) -> Optional[M2Character]:
        """Get a specific character agent.

        Args:
            character_id: The character's ID.

        Returns:
            The character agent or None.
        """
        return self._characters.get(character_id)

    def get_all_character_ids(self) -> List[str]:
        """Get all character IDs (excluding human player).

        Returns:
            List of character IDs.
        """
        return list(self._characters.keys())

    def get_other_characters(self, exclude_id: str) -> List[ScriptCharacter]:
        """Get other characters excluding one.

        Args:
            exclude_id: The character ID to exclude.

        Returns:
            List of other characters.
        """
        return [
            char for char in self.archive.characters
            if char.id != exclude_id
        ]

    async def run_introduction_phase(self) -> Dict[str, str]:
        """Run the introduction phase where all AI characters introduce themselves.

        Returns:
            Dictionary of character_id to introduction text.
        """
        results = {}

        for char_id, agent in self._characters.items():
            response = agent.respond_introduction()
            results[char_id] = response
            self._game_manager.add_discussion(char_id, response)

        return results

    async def broadcast_phase_change(self, new_phase: GamePhase) -> None:
        """Broadcast a phase change to all characters.

        Args:
            new_phase: The new game phase.
        """
        pass

    async def run_discussion_round(
        self,
        user_input: str,
    ) -> Dict[str, str]:
        """Run one round of discussion.

        Args:
            user_input: The human player's input.

        Returns:
            Dictionary of character_id to response.
        """
        phase = self._game_manager.current_phase

        if user_input:
            self._game_manager.add_discussion(self.human_player_id, user_input)

        results = {}
        revealed_clues = self._game_manager.get_revealed_clues()

        for char_id, agent in self._characters.items():
            char_known = self._game_manager.get_player_clues(char_id)
            response = agent.respond(
                user_input=user_input,
                phase=phase,
                known_clues=char_known,
                revealed_clues=revealed_clues,
                other_chars=self.get_other_characters(char_id),
                discussion_history=self._game_manager.state.discussion_history,
            )
            results[char_id] = response
            self._game_manager.add_discussion(char_id, response)

        return results

    async def run_voting(self) -> Dict[str, str]:
        """Run the voting phase where all AI characters vote.

        Returns:
            Dictionary of character_id to their vote (target character ID).
        """
        results = {}

        for char_id, agent in self._characters.items():
            vote = agent.get_vote()
            results[char_id] = vote

            if vote:
                self._game_manager.submit_vote(char_id, vote)

        return results

    def player_speak(self, user_input: str) -> Dict[str, str]:
        """Handle player speaking in discussion.

        This is a synchronous wrapper for run_discussion_round.

        Args:
            user_input: The player's input.

        Returns:
            Dictionary of character_id to response.
        """
        return asyncio.run(self.run_discussion_round(user_input))

    def get_game_state(self) -> GameState:
        """Get the current game state.

        Returns:
            The current GameState.
        """
        return self._game_manager.state

    def get_discussion_history(self) -> List[str]:
        """Get the discussion history.

        Returns:
            List of discussion messages.
        """
        return list(self._game_manager.state.discussion_history)

    def get_clue_board(self) -> Any:
        """Get the clue board for the human player.

        Returns:
            The ClueBoard for the human player.
        """
        return self._game_manager.get_clue_board(self.human_player_id)

    def investigate(self) -> List[Any]:
        """Perform investigation and get random clues.

        Returns:
            List of newly obtained clues.
        """
        return self._game_manager.distribute_random_clues(self.human_player_id)

    def reset(self) -> None:
        """Reset all character agents."""
        for agent in self._characters.values():
            agent.reset()
        self._game_manager.state.discussion_history.clear()
        self._game_manager.state.votes_record.clear()
        self._game_manager.state.phase = GamePhase.INTRODUCTION.value
