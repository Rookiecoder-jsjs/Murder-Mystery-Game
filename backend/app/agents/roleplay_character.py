# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Character roleplay implementation using the OpenAI client directly.

Defaults to DeepSeek V4 Flash with thinking mode disabled — discussion
rounds fire all characters concurrently and want low latency, not deep
reasoning.

Context assembly: every ``respond`` call rebuilds the prompt from the
shared game state (own clues, publicly revealed clues, other characters,
discussion history) plus this character's short private memory. The
private memory only records what this character actually said — votes
and other structured queries bypass it so they never pollute roleplay.
"""

import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from openai import OpenAI
    from app.domain.models import CaseData

from app.core.config import RoleplayConfig, get_config
from app.core.llm_trace import trace_llm_chat
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.core.prompts import PhasePromptTemplates
from app.domain.models import ScriptCharacter, ClueData, GameState


logger = get_logger(__name__)


class RoleplayCharacter:
    """AI character for the murder mystery game.

    Talks to an OpenAI-compatible endpoint (DeepSeek by default) with a
    per-character system prompt built from ``PhasePromptTemplates``.
    """

    def __init__(
        self,
        character: ScriptCharacter,
        client: "OpenAI",
        user_persona: str = "",
        case: Optional["CaseData"] = None,
        config: Optional[RoleplayConfig] = None,
    ):
        """Initialize the roleplay character.

        Args:
            character: The script character to represent.
            client: OpenAI-compatible client configured for roleplay.
            user_persona: Description of who the human player is playing
                (name + public identity). Empty means unknown.
            case: The case data for the story, so the character knows
                which case / era it is inside. Empty means the phase
                prompts render without the case block.
            config: Roleplay config (model name + generation params).
                Falls back to ``get_config().roleplay`` when not provided.
        """
        self.character = character
        self.client = client
        self.user_persona = user_persona or "一位参与游戏的玩家"
        self.case = case
        self.config = config or get_config().roleplay
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

    def _build_system_message(
        self,
        phase: GamePhase,
        case: Optional["CaseData"],
        known_clues: List[ClueData],
        revealed_clues: List[ClueData],
        other_chars: List[ScriptCharacter],
        discussion_history: List[str],
    ) -> str:
        """Build the system prompt for a phase from live game state."""
        if phase == GamePhase.INTRODUCTION:
            return PhasePromptTemplates.introduction_template(self.character, case)
        elif phase == GamePhase.INVESTIGATION:
            return PhasePromptTemplates.investigation_template(
                self.character, case, known_clues, revealed_clues, other_chars
            )
        elif phase == GamePhase.DISCUSSION:
            return PhasePromptTemplates.discussion_template(
                self.character, case, known_clues, revealed_clues,
                other_chars, discussion_history,
            )
        elif phase == GamePhase.VOTING:
            return PhasePromptTemplates.voting_template(
                self.character, case, known_clues, revealed_clues,
                other_chars, discussion_history,
            )
        else:
            return PhasePromptTemplates.base_roleplay_template(self.character, case)

    def _build_messages(
        self,
        user_input: str,
        phase: GamePhase,
        case: Optional["CaseData"],
        known_clues: List[ClueData],
        revealed_clues: List[ClueData],
        other_chars: List[ScriptCharacter],
        discussion_history: List[str],
    ) -> List[Dict[str, str]]:
        """Build messages for the roleplay API.

        The shared discussion history lives in the system prompt (it is
        game state, not this character's memory); the message list keeps
        only this character's own recent exchanges so its replies stay
        in-character across turns.
        """
        system_content = self._build_system_message(
            phase, case, known_clues, revealed_clues, other_chars,
            discussion_history,
        )

        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"你是{self.character.name}。{system_content}\n"
                    f"和你对话的玩家正在扮演：{self.user_persona}\n"
                    f"场景：剧本杀游戏。始终以{self.character.name}的身份说话，"
                    f"不要在回复开头重复自己的名字。"
                ),
            }
        ]

        for entry in self.conversation_history[-20:]:
            messages.append({
                "role": entry["role"],
                "content": entry["message"],
            })

        if user_input:
            messages.append({
                "role": "user",
                "content": user_input,
            })
        else:
            # 无玩家输入时的占位消息 —— 按阶段给语义正确的指令，
            # 避免投票/引言阶段被一句泛化的"继续角色扮演"带偏输出。
            phase_prompt = {
                GamePhase.INTRODUCTION: "请开始你的自我介绍。",
                GamePhase.VOTING: "请根据投票任务直接给出你的投票目标，只输出角色ID。",
            }.get(phase, "请继续你的角色扮演。")
            messages.append({
                "role": "user",
                "content": phase_prompt,
            })

        return messages

    def _create_completion(self, messages: List[Dict[str, str]]):
        """Call the chat completion API with roleplay generation params.

        Thinking mode is toggled per ``config.thinking_enabled`` — it is
        off by default so concurrent replies stay fast. Note that with
        thinking enabled the API silently ignores temperature/top_p.
        """
        return self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.generation.temperature,
            top_p=self.config.generation.top_p,
            max_tokens=self.config.generation.max_completion_tokens,
            extra_body={
                "thinking": {
                    "type": "enabled" if self.config.thinking_enabled else "disabled"
                }
            },
        )

    def respond(
        self,
        user_input: str,
        phase: GamePhase,
        known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
        discussion_history: Optional[List[str]] = None,
        case: Optional["CaseData"] = None,
        record_in_memory: bool = True,
    ) -> str:
        """Generate a response using live game context.

        Args:
            user_input: The user's input message (empty to let the
                character speak on its own).
            phase: Current game phase.
            case: Case data for the case block; falls back to the
                character-level ``self.case`` when not provided.
            known_clues: Clues known to this character.
            revealed_clues: Globally revealed clues.
            other_chars: All characters (filtered internally).
            discussion_history: Shared discussion log ("名字: 发言" lines).
            record_in_memory: Append the exchange to this character's
                private history. Structured queries (votes) pass False.

        Returns:
            The character's response.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        all_chars = other_chars or []
        discussion_history = discussion_history or []

        effective_case = case if case is not None else self.case
        messages = self._build_messages(
            user_input,
            phase,
            effective_case,
            known_clues,
            revealed_clues,
            [c for c in all_chars if c.id != self.character.id],
            discussion_history,
        )

        start = time.monotonic()
        trace_context = {
            "character_id": self.character_id,
            "character_name": self.name,
            "phase": phase.value,
        }
        reasoning = ""
        try:
            response = self._create_completion(messages)
            message = response.choices[0].message
            content = message.content
            reasoning = getattr(message, "reasoning_content", "") or ""
            if content is None:
                content = "[无回复]"
        except Exception as e:
            trace_llm_chat(
                model=self.config.model_name,
                kind="roleplay",
                messages=messages,
                context=trace_context,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
            logger.error("[Roleplay Error] %s: %s", self.name, e)
            return "[回复失败]"

        trace_llm_chat(
            model=self.config.model_name,
            kind="roleplay",
            messages=messages,
            context=trace_context,
            response=content,
            reasoning=reasoning,
            usage=getattr(response, "usage", None),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

        clean_content = self._strip_self_prefix(content)

        if record_in_memory and user_input:
            self.conversation_history.append({
                "role": "user",
                "message": user_input,
            })
        if record_in_memory:
            self.conversation_history.append({
                "role": "assistant",
                "message": clean_content,
            })

        return clean_content

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
        return self.respond("", GamePhase.INTRODUCTION, record_in_memory=False)

    def get_vote(
        self,
        known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
        discussion_history: Optional[List[str]] = None,
    ) -> str:
        """Get a vote target from live game state.

        Parses either a character ID (char_X) or a character name from
        the reply; returns an empty string when neither appears. Does
        not touch the conversation memory.

        Returns:
            The voted character ID, or "" when unparseable.
        """
        result = self.respond(
            "",
            GamePhase.VOTING,
            known_clues=known_clues,
            revealed_clues=revealed_clues,
            other_chars=other_chars,
            discussion_history=discussion_history,
            record_in_memory=False,
        )
        return self.parse_vote_target(result, other_chars or [])

    @staticmethod
    def parse_vote_target(
        text: str,
        other_chars: List[ScriptCharacter],
    ) -> str:
        """Extract a voted character ID from free-form reply text.

        Matches a char_X pattern first; otherwise matches one of the
        candidate names anywhere in the text. Names are checked longest
        first so overlapping names resolve deterministically.

        Returns:
            The character ID, or "" when nothing matches.
        """
        id_match = re.search(r'char_\d+', text)
        if id_match:
            return id_match.group()

        by_name = {
            c.name: c.id for c in other_chars
        }
        for name in sorted(by_name, key=len, reverse=True):
            if name and name in text:
                return by_name[name]
        return ""

    def reset(self) -> None:
        """Reset conversation history."""
        self.conversation_history = []
