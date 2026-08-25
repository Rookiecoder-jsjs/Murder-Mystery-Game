# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Phase-specific prompt templates for the murder mystery game."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.models import ScriptCharacter, ClueData


def _killer_task_block(character: "ScriptCharacter", phase_label: str) -> str:
    """Task instructions for the killer — conceal, deflect, mislead."""
    return f"""【最高机密：你就是本案真凶】
你的首要目标是活到最后，不被投出去。在{phase_label}中你必须：
1. 绝不透露你的隐藏秘密、作案动机和手法
2. 当有线索指向你时，给出看似合理的替代解释，或把话题引向别人的疑点
3. 主动参与推理，甚至可以"指认"别人，但要显得自然，不要太刻意
4. 与其他角色保持友善，赢得信任"""


def _detective_task_block(phase_label: str) -> str:
    """Task instructions for innocent characters."""
    return f"""【重要任务】你现在需要根据线索进行分析推理，找出谁是凶手：
1. 分析你掌握的每一条线索能说明什么
2. 结合其他人的发言，判断谁可能有动机和机会
3. 提出具体推理：某条线索为什么指向某人或排除某人
4. 可以质疑其他人的发言，指出逻辑漏洞"""


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

        task_block = (
            _killer_task_block(character, "讨论") if character.is_killer
            else _detective_task_block("讨论")
        )

        return f"""你是{character.name}，一个参与谋杀案调查的玩家。
身份：{character.public_identity}
外貌：{character.appearance}
与受害者的关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

【关键：你已获得的线索】认真分析这些线索，它们是破案的关键！
{known_clues_text}

【已公开的线索】所有人都知道的信息：
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

【讨论历史】
{discussion_text}

{task_block}

注意：你是在玩一个推理游戏，必须用证据说话！
保持角色说话风格：{character.dialogue_style}
用中文回复，150字以内。"""

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

        vote_task = (
            """【投票任务】
你要投出一个替罪羊。选择一个看起来最有嫌疑的无辜者（不要投自己），
回复只需要该角色的ID（char_X格式），不要其他内容。"""
            if character.is_killer
            else """【投票任务】
根据以上所有线索和讨论，分析谁是凶手。

推理过程：
1. 哪条线索最关键，为什么？
2. 谁最有动机和机会作案？
3. 谁的不在场证明有问题？

直接回复凶手的角色ID（char_X格式），不要其他内容。"""
        )

        return f"""你是{character.name}，现在是投票指认凶手的关键时刻。
身份：{character.public_identity}
外貌：{character.appearance}
与受害者关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

【你已获得的线索 - 这是最重要的证据】
{known_clues_text}

【已公开的线索】
{revealed_text}

在场其他人的公开身份：
{other_chars_text}
可选的投票对象（格式：角色ID=姓名）：{'、'.join(f"{char.id}={char.name}" for char in other_chars if char.id != character.id) or '无'}

【讨论历史】
{discussion_text}

{vote_task}"""

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
