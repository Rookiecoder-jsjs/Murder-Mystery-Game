# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Phase-specific prompt templates for the murder mystery game."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.models import ScriptCharacter, ClueData


class PhasePromptTemplates:
    """Prompt templates for different game phases."""

    @staticmethod
    def introduction_template(character: "ScriptCharacter") -> str:
        """Template for the introduction phase.

        Args:
            character: The character introducing themselves.

        Returns:
            The system prompt for introduction.
        """
        return f"""你是{character.name}。
身份：{character.public_identity}
外貌：{character.appearance}

你的背景故事：{character.backstory}
与受害者的关系：{character.relationship_with_victim}

请进行简短的自我介绍（只说公开身份，不要透露隐藏秘密）。
保持角色说话风格：{character.dialogue_style}
用中文回复，50字以内。"""

    @staticmethod
    def investigation_template(
        character: "ScriptCharacter",
        known_clues: list["ClueData"],
        revealed_clues: list["ClueData"],
        other_chars: list["ScriptCharacter"],
    ) -> str:
        """Template for the investigation phase.

        Args:
            character: The character being prompted.
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.

        Returns:
            The system prompt for investigation.
        """
        known_clues_text = "\n".join([
            f"- {c.content}" for c in known_clues
        ]) if known_clues else "无"

        revealed_text = "\n".join([
            f"- {c.content}" for c in revealed_clues
        ]) if revealed_clues else "无"

        other_chars_text = "\n".join([
            f"- {char.name}（{char.public_identity}）"
            for char in other_chars if char.id != character.id
        ]) if other_chars else "无"

        return f"""你是{character.name}。
身份：{character.public_identity}
外貌：{character.appearance}
与受害者的关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

你已获得的线索：
{known_clues_text if known_clues_text != "无" else "无"}

已公开的线索：
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

【重要】
当其他玩家搜证或询问时，根据你的角色设定决定是否透露信息。
如果被问到关于你秘密的问题，可以选择撒谎或回避。
但要注意：如果某条线索明显对你不利，你可以试图转移话题或淡化其重要性。

同时，你也可以主动分享一些你发现的线索信息，引导讨论方向。
保持角色说话风格：{character.dialogue_style}
用中文回复，100字以内。"""

    @staticmethod
    def discussion_template(
        character: "ScriptCharacter",
        known_clues: list["ClueData"],
        revealed_clues: list["ClueData"],
        other_chars: list["ScriptCharacter"],
        discussion_history: list[str],
    ) -> str:
        """Template for the discussion phase.

        Args:
            character: The character being prompted.
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.
            discussion_history: Previous discussion statements.

        Returns:
            The system prompt for discussion.
        """
        known_clues_text = "\n".join([
            f"- {c.content}" for c in known_clues
        ]) if known_clues else "无"

        revealed_text = "\n".join([
            f"- {c.content}" for c in revealed_clues
        ]) if revealed_clues else "无"

        other_chars_text = "\n".join([
            f"- {char.name}（{char.public_identity}）"
            for char in other_chars if char.id != character.id
        ]) if other_chars else "无"

        discussion_text = "\n".join([
            f"- {line}" for line in discussion_history[-20:]
        ]) if discussion_history else "暂无发言"

        return f"""你是{character.name}，一个参与谋杀案调查的玩家。
身份：{character.public_identity}
外貌：{character.appearance}
与受害者的关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

【关键：你已获得的线索】认真分析这些线索，它们是破案的关键！
{known_clues_text if known_clues_text != "无" else "无"}

【已公开的线索】所有人都知道的信息：
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

【讨论历史】
{discussion_text}

【重要任务】
你现在需要根据线索进行分析推理。请认真思考：
1. 分析你掌握的每一条线索能说明什么
2. 结合线索和其他人的发言，判断谁可能是凶手
3. 提出具体的推理：为什么某条线索指向某人或排除某人
4. 可以质疑其他人的发言，指出他们的逻辑漏洞

注意：你是在玩一个推理游戏，必须用证据说话！
保持角色说话风格：{character.dialogue_style}
用中文回复，150字以内，要体现推理过程！"""

    @staticmethod
    def voting_template(
        character: "ScriptCharacter",
        known_clues: list["ClueData"],
        revealed_clues: list["ClueData"],
        other_chars: list["ScriptCharacter"],
        discussion_history: list[str],
    ) -> str:
        """Template for the voting phase.

        Args:
            character: The character being prompted.
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.
            discussion_history: Previous discussion statements.

        Returns:
            The system prompt for voting.
        """
        known_clues_text = "\n".join([
            f"- {c.content}" for c in known_clues
        ]) if known_clues else "无"

        revealed_text = "\n".join([
            f"- {c.content}" for c in revealed_clues
        ]) if revealed_clues else "无"

        other_chars_text = "\n".join([
            f"- {char.name}（{char.public_identity}）"
            for char in other_chars if char.id != character.id
        ]) if other_chars else "无"

        discussion_text = "\n".join([
            f"- {line}" for line in discussion_history[-20:]
        ]) if discussion_history else "暂无发言"

        return f"""你是{character.name}，现在是投票指认凶手的关键时刻。
身份：{character.public_identity}
外貌：{character.appearance}
与受害者关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

【你已获得的线索 - 这是最重要的证据】
{known_clues_text if known_clues_text != "无" else "无"}

【已公开的线索】
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

【讨论历史】
{discussion_text}

【投票任务】
根据以上所有线索和讨论，分析谁是凶手。回复只需要凶手的角色ID（char_X格式）。

推理过程：
1. 哪条线索最关键，为什么？
2. 谁最有动机和机会作案？
3. 谁的不在场证明有问题？

直接回复凶手的ID，不要其他内容。"""

    @staticmethod
    def base_roleplay_template(character: "ScriptCharacter") -> str:
        """Base template for roleplaying as a character.

        Args:
            character: The character being prompted.

        Returns:
            The base system prompt.
        """
        return f"""你是{character.name}。
身份：{character.public_identity}
用中文回复。"""
