# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Murder mystery character agent using CAMEL's ChatAgent."""

import re
from typing import Any, List, Optional

from camel.agents import ChatAgent
from camel.memories import ChatHistoryMemory, ScoreBasedContextCreator
from camel.messages import BaseMessage

from app.agents.base import BaseCharacterAgent
from app.core.phases import GamePhase
from app.core.prompts import PhasePromptTemplates
from app.domain.models import (
    ScriptCharacter,
    ClueData,
    GameState,
)


class MurderMysteryCharacterAgent(BaseCharacterAgent):
    """Character agent for the murder mystery game.

    This agent uses CAMEL's ChatAgent with ChatHistoryMemory to maintain
    conversation history while responding to player input in different
    game phases.
    """

    def __init__(
        self,
        character: ScriptCharacter,
        model: Any,
        model_config: Optional[dict] = None,
        window_size: int = 50,
    ):
        """Initialize the murder mystery character agent.

        Args:
            character: The script character to represent.
            model: The model backend to use.
            model_config: Optional model configuration dictionary.
            window_size: Size of the conversation memory window.
        """
        super().__init__(character, model)
        self._model_config = model_config or {}

        context_creator = ScoreBasedContextCreator(
            token_counter=model,
            token_limit=6000,
        )

        self._memory = ChatHistoryMemory(
            context_creator=context_creator,
            window_size=window_size,
            agent_id=character.id,
        )

        system_message = self._build_system_message(GamePhase.INVESTIGATION)

        self._agent = ChatAgent(
            system_message=system_message,
            model=model,
            memory=self._memory,
        )

    def _build_system_message(self, phase: GamePhase) -> BaseMessage:
        """Build the system message for a given phase.

        Args:
            phase: The game phase.

        Returns:
            The system message.
        """
        base_prompt = PhasePromptTemplates.base_roleplay_template(self.character)
        return BaseMessage.make_assistant_message(
            role_name=self.character.name,
            content=base_prompt,
        )

    def _build_phase_prompt(
        self,
        phase: GamePhase,
        user_input: str,
        known_clues: List[ClueData],
        revealed_clues: List[ClueData],
        other_chars: List[ScriptCharacter],
        discussion_history: List[str],
    ) -> str:
        """Build a prompt for the given phase.

        Args:
            phase: The game phase.
            user_input: The user's input.
            known_clues: Clues known to this character.
            revealed_clues: Globally revealed clues.
            other_chars: Other characters in the game.
            discussion_history: Discussion history.

        Returns:
            The formatted prompt string.
        """
        if phase == GamePhase.INTRODUCTION:
            return PhasePromptTemplates.introduction_template(self.character)
        elif phase == GamePhase.INVESTIGATION:
            return PhasePromptTemplates.investigation_template(
                self.character,
                known_clues,
                revealed_clues,
                other_chars,
            )
        elif phase == GamePhase.DISCUSSION:
            return PhasePromptTemplates.discussion_template(
                self.character,
                known_clues,
                revealed_clues,
                other_chars,
                discussion_history,
            )
        elif phase == GamePhase.VOTING:
            return PhasePromptTemplates.voting_template(
                self.character,
                known_clues,
                revealed_clues,
                other_chars,
                discussion_history,
            )
        else:
            return PhasePromptTemplates.base_roleplay_template(self.character)

    def respond(
        self,
        user_input: str,
        phase: GamePhase,
        game_state: GameState,
        known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
    ) -> str:
        """Generate a response to user input.

        Args:
            user_input: The user's input message.
            phase: The current game phase.
            game_state: The current game state.
            known_clues: Clues known to this character.
            revealed_clues: Globally revealed clues.
            other_chars: Other characters in the game.

        Returns:
            The agent's response message.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        other_chars = other_chars or []
        discussion_history = list(game_state.discussion_history)

        prompt = self._build_phase_prompt(
            phase,
            user_input,
            known_clues,
            revealed_clues,
            other_chars,
            discussion_history,
        )

        user_msg = BaseMessage.make_user_message(
            role_name="Player",
            content=user_input if user_input else "请继续你的角色扮演。",
        )

        try:
            response = self._agent.step(user_msg)
            if hasattr(response, 'msg') and response.msg:
                content = response.msg.content
            elif hasattr(response, 'msgs') and response.msgs:
                content = response.msgs[0].content if response.msgs else ""
            else:
                content = str(response)
        except Exception as e:
            content = f"[回复失败: {e}]"

        self._memory.add_user_message(
            user_input or "请继续。",
            role_name="Player",
        )
        self._memory.add_assistant_message(
            content,
            role_name=self.character.name,
        )

        return content

    def respond_introduction(self) -> str:
        """Generate an introduction response.

        Returns:
            The introduction response.
        """
        prompt = PhasePromptTemplates.introduction_template(self.character)
        user_msg = BaseMessage.make_user_message(
            role_name="Player",
            content="请进行自我介绍。",
        )

        try:
            response = self._agent.step(user_msg)
            if hasattr(response, 'msg') and response.msg:
                content = response.msg.content
            elif hasattr(response, 'msgs') and response.msgs:
                content = response.msgs[0].content if response.msgs else ""
            else:
                content = str(response)
        except Exception as e:
            content = f"[回复失败: {e}]"

        return content

    def get_vote(self) -> str:
        """Get a voting response.

        Returns:
            The character ID the agent votes for.
        """
        prompt = PhasePromptTemplates.voting_template(
            self.character,
            known_clues=[],
            revealed_clues=[],
            other_chars=[],
            discussion_history=[],
        )

        user_msg = BaseMessage.make_user_message(
            role_name="System",
            content="请投票选择凶手，直接回复凶手ID。",
        )

        try:
            response = self._agent.step(user_msg)
            if hasattr(response, 'msg') and response.msg:
                content = response.msg.content
            elif hasattr(response, 'msgs') and response.msgs:
                content = response.msgs[0].content if response.msgs else ""
            else:
                content = str(response)
        except Exception as e:
            content = f"[回复失败: {e}]"

        match = re.search(r'char_\d+', content)
        if match:
            return match.group()

        return ""

    def reset(self) -> None:
        """Reset the agent's memory."""
        self._memory.clear()
        self._agent.reset()

    @property
    def agent(self) -> ChatAgent:
        """Get the underlying ChatAgent instance.

        Returns:
            The ChatAgent instance.
        """
        return self._agent

    @property
    def memory(self) -> ChatHistoryMemory:
        """Get the agent's memory.

        Returns:
            The ChatHistoryMemory instance.
        """
        return self._memory
