# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game service for managing murder mystery game sessions."""

from typing import Any, Dict, List, Optional

from app.core.phases import GamePhase
from app.domain.models import StoryArchive, GameState, ClueBoard
from app.workforce.game_workforce import MurderMysteryWorkforce


class GameSession:
    """Represents a single murder mystery game session."""

    def __init__(
        self,
        session_id: str,
        archive: StoryArchive,
        human_player_id: str,
        workforce: MurderMysteryWorkforce,
    ):
        """Initialize a game session.

        Args:
            session_id: Unique session identifier.
            archive: The story archive.
            human_player_id: The human player's character ID.
            workforce: The game workforce.
        """
        self.session_id = session_id
        self.archive = archive
        self.human_player_id = human_player_id
        self.workforce = workforce

    @property
    def game_manager(self):
        """Get the game manager."""
        return self.workforce.game_manager

    @property
    def state(self) -> GameState:
        """Get the current game state."""
        return self.workforce.get_game_state()

    @property
    def phase(self) -> GamePhase:
        """Get the current phase."""
        return GamePhase(self.state.phase)

    @property
    def is_game_ended(self) -> bool:
        """Check if game has ended."""
        return self.state.game_ended


class GameService:
    """Service for managing murder mystery game sessions."""

    def __init__(self, m2_client: Any):
        """Initialize the game service.

        Args:
            m2_client: The OpenAI client for M2-her (character roleplay).
        """
        self._m2_client = m2_client
        self._sessions: Dict[str, GameSession] = {}
        self._session_counter = 0

    def create_session(
        self,
        archive: StoryArchive,
        human_player_id: str,
    ) -> GameSession:
        """Create a new game session.

        Args:
            archive: The story archive.
            human_player_id: The human player's character ID.

        Returns:
            The created GameSession.
        """
        self._session_counter += 1
        session_id = f"session_{self._session_counter}"

        workforce = MurderMysteryWorkforce(
            archive=archive,
            human_player_id=human_player_id,
            model_config={},
        )

        workforce.initialize_characters(self._m2_model)
        workforce.setup_workforce(self._m2_model)

        session = GameSession(
            session_id=session_id,
            archive=archive,
            human_player_id=human_player_id,
            workforce=workforce,
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The GameSession or None.
        """
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> bool:
        """Remove a session.

        Args:
            session_id: The session ID.

        Returns:
            True if removed.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[str]:
        """List all session IDs.

        Returns:
            List of session IDs.
        """
        return list(self._sessions.keys())

    async def introduce_phase(self, session_id: str) -> Dict[str, str]:
        """Run the introduction phase.

        Args:
            session_id: The session ID.

        Returns:
            Dictionary of character_id to introduction.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return await session.workforce.run_introduction_phase()

    async def discuss(
        self,
        session_id: str,
        user_input: str,
    ) -> Dict[str, str]:
        """Run a discussion round.

        Args:
            session_id: The session ID.
            user_input: The player's input.

        Returns:
            Dictionary of character_id to response.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return await session.workforce.run_discussion_round(user_input)

    async def vote_phase(self, session_id: str) -> Dict[str, str]:
        """Run the voting phase.

        Args:
            session_id: The session ID.

        Returns:
            Dictionary of character_id to vote.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return await session.workforce.run_voting()

    def investigate(self, session_id: str) -> List[Any]:
        """Perform investigation.

        Args:
            session_id: The session ID.

        Returns:
            List of obtained clues.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.workforce.investigate()

    def get_clue_board(self, session_id: str) -> ClueBoard:
        """Get the clue board for the human player.

        Args:
            session_id: The session ID.

        Returns:
            ClueBoard for the human player.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.workforce.get_clue_board()

    def submit_vote(
        self,
        session_id: str,
        target_id: str,
    ) -> bool:
        """Submit the human player's vote.

        Args:
            session_id: The session ID.
            target_id: The voted character's ID.

        Returns:
            True if vote was recorded.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.game_manager.submit_vote(
            session.human_player_id,
            target_id,
        )

    def check_voting_result(self, session_id: str) -> tuple[bool, str]:
        """Check the voting result.

        Args:
            session_id: The session ID.

        Returns:
            (game_ended, result_description)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.game_manager.check_voting_result()

    def accuse(
        self,
        session_id: str,
        target_id: str,
    ) -> tuple[bool, str]:
        """Player accuses a character.

        Args:
            session_id: The session ID.
            target_id: The accused character's ID.

        Returns:
            (is_correct, result_description)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.game_manager.accuse(
            session.human_player_id,
            target_id,
        )

    def next_phase(self, session_id: str) -> GamePhase:
        """Advance to the next phase.

        Args:
            session_id: The session ID.

        Returns:
            The new phase.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.game_manager.next_phase()

    def set_phase(self, session_id: str, phase: GamePhase) -> None:
        """Set the current phase.

        Args:
            session_id: The session ID.
            phase: The phase to set.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.game_manager.set_phase(phase)

    def get_game_summary(self, session_id: str) -> str:
        """Get the game summary.

        Args:
            session_id: The session ID.

        Returns:
            Game summary string.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.game_manager.get_game_summary()

    def get_state(self, session_id: str) -> GameState:
        """Get the current game state.

        Args:
            session_id: The session ID.

        Returns:
            The GameState.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return session.state
