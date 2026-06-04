# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""M2-her character implementation using OpenAI client directly."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from openai import OpenAI

from app.core.config import MiniMaxConfig, get_config
from app.core.phases import GamePhase
from app.core.prompts import PhasePromptTemplates
from app.core.logging import get_logger
from app.domain.models import ScriptCharacter, ClueData, GameState


logger = get_logger(__name__)


class M2Character:
    """M2-her character for the murder mystery game.

    This class provides character roleplay using OpenAI client directly
    with M2-her model, similar to the approach in four_person_chat.py.
    """

    def __init__(
        self,
        character: ScriptCharacter,
        client: "OpenAI",
        user_persona: str = "一个普通用户",
        config: Optional[MiniMaxConfig] = None,
    ):
        """Initialize the M2 character.

        Args:
            character: The script character to represent.
            client: OpenAI client configured for M2-her.
            user_persona: Description of the user's role.
            config: MiniMax config (model name + generation params).
                Falls back to ``get_config().minimax`` when not provided.
        """
        self.character = character
        self.client = client
        self.user_persona = user_persona
        self.config = config or get_config().minimax
        self.conversation_history: List[Dict[str, str]] = []

    @property
    def name(self) -> str:
        """Get the character name."""
        return self.character.name

    @property
    def character_id(self) -> str:
        """Get the character ID."""
        return self.character.id

    @property
    def is_killer(self) -> bool:
        """Check if this character is the killer."""
        return self.character.is_killer

    def _build_system_message(self, phase: GamePhase) -> str:
        """Build the system prompt for a phase.

        Args:
            phase: The current game phase.

        Returns:
            System prompt string.
        """
        if phase == GamePhase.INTRODUCTION:
            return PhasePromptTemplates.introduction_template(self.character)
        elif phase == GamePhase.INVESTIGATION:
            return PhasePromptTemplates.investigation_template(
                self.character, [], [], []
            )
        elif phase == GamePhase.DISCUSSION:
            return PhasePromptTemplates.discussion_template(
                self.character, [], [], [], []
            )
        elif phase == GamePhase.VOTING:
            return PhasePromptTemplates.voting_template(
                self.character, [], [], [], []
            )
        else:
            return PhasePromptTemplates.base_roleplay_template(self.character)

    def _build_messages(
        self,
        user_input: str,
        phase: GamePhase,
        known_clues: List[ClueData],
        revealed_clues: List[ClueData],
        other_chars: List[ScriptCharacter],
        discussion_history: List[str],
    ) -> List[Dict[str, str]]:
        """Build messages for M2-her API.

        Args:
            user_input: The user's input.
            phase: Current game phase.
            known_clues: Clues known to this character.
            revealed_clues: Globally revealed clues.
            other_chars: Other characters.
            discussion_history: Discussion history.

        Returns:
            List of message dictionaries.
        """
        system_content = self._build_system_message(phase)

        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"你是{self.character.name}。{system_content}\n"
                    f"用户的人设是：{self.user_persona}\n"
                    f"场景：剧本杀游戏"
                ),
            }
        ]

        for entry in self.conversation_history[-30:]:
            if entry["role"] == "user":
                messages.append({
                    "role": "user",
                    "content": f"{entry['speaker']}说：{entry['message']}",
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": f"{entry['speaker']}说：{entry['message']}",
                })

        if user_input:
            messages.append({
                "role": "user",
                "content": user_input,
            })
        else:
            messages.append({
                "role": "user",
                "content": "请继续你的角色扮演。",
            })

        return messages

    def respond(
        self,
        user_input: str,
        phase: GamePhase,
        known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
        discussion_history: Optional[List[str]] = None,
    ) -> str:
        """Generate a response.

        Args:
            user_input: The user's input message.
            phase: Current game phase.
            known_clues: Clues known to this character.
            revealed_clues: Globally revealed clues.
            other_chars: Other characters.
            discussion_history: Discussion history.

        Returns:
            The character's response.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        other_chars = other_chars or []
        discussion_history = discussion_history or []

        messages = self._build_messages(
            user_input,
            phase,
            known_clues,
            revealed_clues,
            other_chars,
            discussion_history,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=self.config.generation.temperature,
                top_p=self.config.generation.top_p,
                max_completion_tokens=self.config.generation.max_completion_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                content = "[无回复]"
        except Exception as e:
            logger.error("[M2-her Error] %s: %s", self.name, e)
            content = "[回复失败]"

        clean_content = self._strip_self_prefix(content)

        if user_input:
            self.conversation_history.append({
                "role": "user",
                "speaker": "玩家",
                "message": user_input,
            })

        self.conversation_history.append({
            "role": "assistant",
            "speaker": self.name,
            "message": clean_content,
        })

        return content

    def _strip_self_prefix(self, content: str) -> str:
        """Remove a self-introduction prefix if the model emitted one.

        Models occasionally prefix replies with their own name (e.g.
        "Alice说：..."). Strip the first line if it matches, so the
        client doesn't render the name twice. Also handles the bare-name
        variant "Alice:" used by some models.
        """
        for prefix in (
            f"{self.name}说：",
            f"{self.name}说:",
            f"{self.name}:",
            f"{self.name}：",
        ):
            if content.startswith(prefix):
                return content[len(prefix):].lstrip()
        # Multi-line: drop the first line if it's only a name+colon
        first, _, rest = content.partition("\n")
        if first.rstrip(":：").strip() == self.name:
            return rest.lstrip()
        return content

    def respond_introduction(self) -> str:
        """Generate an introduction response.

        Returns:
            The introduction.
        """
        return self.respond("", GamePhase.INTRODUCTION)

    def get_vote(self) -> str:
        """Get a voting response.

        Returns:
            The character ID voted for.
        """
        import re

        result = self.respond(
            "",
            GamePhase.VOTING,
            known_clues=[],
            revealed_clues=[],
            other_chars=[],
            discussion_history=[],
        )

        match = re.search(r'char_\d+', result)
        if match:
            return match.group()

        return ""

    def reset(self) -> None:
        """Reset conversation history."""
        self.conversation_history = []
