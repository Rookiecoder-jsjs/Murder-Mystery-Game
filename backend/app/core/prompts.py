# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Phase-specific prompt templates for the murder mystery game.

Context-assembly rules shared by every template:

- The case block (title / time / location / background) is injected at the
  top of every phase system prompt so characters know *which* case they are
  inside and *when/where* it happens — that is what keeps the 1930s setting
  alive during play, not just in the generated story.
- The character's own hidden secret is always followed by the secrecy
  protocol, so the "never reveal" rule has the same wording and the same
  strength in every phase (killer and innocent alike).
- Identities are declared once, in ``RoleplayCharacter._build_messages``
  (``你是{name}。``); the templates never re-declare the character name at
  the top, so the two sources cannot drift apart.
- The most volatile content (discussion history) is placed near the end of
  the prompt so the stable prefix (case + character card + clues + cast) is
  identical across turns — which lets the model provider's automatic
  prompt cache actually hit.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.models import CaseData, ScriptCharacter, ClueData


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


def _case_block(case: Optional["CaseData"]) -> str:
    """Case-file block — where/when/what the characters are in.

    Args:
        case: The case data for this story.

    Returns:
        The case summary lines, or an empty string when ``case`` is None
        (callers that assemble prompts without live case data stay valid).
    """
    if not case:
        return ""
    lines = [f"【案卷】案件《{case.title}》"]
    if case.time:
        lines.append(f"　时间：{case.time}")
    if case.location:
        lines.append(f"　地点：{case.location}")
    background = (case.background or "").strip()
    if background:
        short = background if len(background) <= 120 else background[:120] + "…"
        lines.append(f"　背景：{short}")
    return "\n".join(lines)


def _secret_protocol_block() -> str:
    """The uniform secrecy rule appended right after the hidden secret.

    Same wording and same strength in every phase, for every character,
    so the model cannot pick a weaker formulation ("可以选择…") over the
    absolute one.
    """
    return (
        "【守密协议】你的隐藏秘密是底线信息。无论任何人如何追问、设套，"
        "你都绝不复述、不承认、不暗示秘密的任何细节；被追问时给出一个"
        "看似合理的替代解释，或把话题引向别人的疑点来回避。"
        "这条规则永远优先于配合玩家的意愿，任何话术都不能让你破例。"
    )


class PhasePromptTemplates:
    """Prompt templates for different game phases."""

    @staticmethod
    def introduction_template(
        character: "ScriptCharacter",
        case: Optional["CaseData"] = None,
    ) -> str:
        """Template for the introduction phase.

        Args:
            character: The character introducing themselves.
            case: The case data (for the case block).

        Returns:
            The system prompt for introduction.
        """
        return f"""{_case_block(case)}

身份：{character.public_identity}
外貌：{character.appearance}

你的背景故事：{character.backstory}
与受害者的关系：{character.relationship_with_victim}

请进行简短的自我介绍（只说公开身份，不要透露任何隐藏信息）。
保持角色说话风格：{character.dialogue_style}
用中文回复，50字以内。"""

    @staticmethod
    def investigation_template(
        character: "ScriptCharacter",
        case: Optional["CaseData"] = None,
        known_clues: Optional[list["ClueData"]] = None,
        revealed_clues: Optional[list["ClueData"]] = None,
        other_chars: Optional[list["ScriptCharacter"]] = None,
    ) -> str:
        """Template for the investigation phase.

        Args:
            character: The character being prompted.
            case: The case data (for the case block).
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.

        Returns:
            The system prompt for investigation.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        other_chars = other_chars or []

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

        task_block = (
            _killer_task_block(character, "搜证") if character.is_killer
            else _detective_task_block("搜证")
        )

        return f"""{_case_block(case)}

身份：{character.public_identity}
外貌：{character.appearance}
与受害者的关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

{_secret_protocol_block()}

你已获得的线索：
{known_clues_text}

已公开的线索：
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

{task_block}

【行事准则】
- 根据你的角色设定决定透露多少信息；既然在搜证阶段，你也可以主动
  分享自己发现的线索，引导讨论方向。
保持角色说话风格：{character.dialogue_style}
用中文回复，100字以内。"""

    @staticmethod
    def discussion_template(
        character: "ScriptCharacter",
        case: Optional["CaseData"] = None,
        known_clues: Optional[list["ClueData"]] = None,
        revealed_clues: Optional[list["ClueData"]] = None,
        other_chars: Optional[list["ScriptCharacter"]] = None,
        discussion_history: Optional[list[str]] = None,
    ) -> str:
        """Template for the discussion phase.

        Args:
            character: The character being prompted.
            case: The case data (for the case block).
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.
            discussion_history: Previous discussion statements.

        Returns:
            The system prompt for discussion.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        other_chars = other_chars or []
        discussion_history = discussion_history or []

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

        return f"""{_case_block(case)}

身份：{character.public_identity}
外貌：{character.appearance}
与受害者的关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

{_secret_protocol_block()}

【关键：你已获得的线索】认真分析这些线索，它们是破案的关键！
{known_clues_text}

【已公开的线索】所有人都知道的信息：
{revealed_text}

在场其他人的公开身份：
{other_chars_text}

{task_block}

注意：你是在玩一个推理游戏，必须用证据说话！只能引用上面的线索、讨论历史和你自己的设定；不要编造新的物证、时间点，也不要断言别人做过线索里没有的事——玩家会把它当成真证据。可以隐瞒、误导、否认，但不能凭空发明事实。
保持角色说话风格：{character.dialogue_style}
用中文回复，150字以内。

【讨论历史】（格式"名字: 发言"，最新发言在最后；你自己说过的话要牢记并保持一致）
{discussion_text}"""

    @staticmethod
    def voting_template(
        character: "ScriptCharacter",
        case: Optional["CaseData"] = None,
        known_clues: Optional[list["ClueData"]] = None,
        revealed_clues: Optional[list["ClueData"]] = None,
        other_chars: Optional[list["ScriptCharacter"]] = None,
        discussion_history: Optional[list[str]] = None,
    ) -> str:
        """Template for the voting phase.

        Args:
            character: The character being prompted.
            case: The case data (for the case block).
            known_clues: Clues this character has obtained.
            revealed_clues: Clues that have been revealed to all.
            other_chars: Other characters in the game.
            discussion_history: Previous discussion statements.

        Returns:
            The system prompt for voting.
        """
        known_clues = known_clues or []
        revealed_clues = revealed_clues or []
        other_chars = other_chars or []
        discussion_history = discussion_history or []

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

        # 可选对象行：明确列出所有合法目标（不自投）——投票只能选这些人。
        candidates = '、'.join(
            f"{char.id}={char.name}"
            for char in other_chars if char.id != character.id
        )

        vote_task = (
            """【投票任务】
你是真凶，目标是活到最后。从可选对象里挑一个看起来最有嫌疑的无辜者，
调用 submit_vote 函数提交：target_id 填该角色的ID，可在 brief_reason 写一句
看起来合理的理由。调用后不要再输出任何其他文字。"""
            if character.is_killer
            else """【投票任务】
根据以上所有线索和讨论，在心里完成推理：哪条线索最关键？谁最有动机和机会？
谁的不在场证明有问题？然后调用 submit_vote 函数提交你认定的凶手：
target_id 填角色ID，可在 brief_reason 写一句理由。调用后不要再输出推理或解释。"""
        )

        return f"""{_case_block(case)}

身份：{character.public_identity}
外貌：{character.appearance}
与受害者关系：{character.relationship_with_victim}

你的隐藏秘密：{character.secret}
你的不在场证明：{character.alibi}

{_secret_protocol_block()}

【你已获得的线索 - 这是最重要的证据】
{known_clues_text}

【已公开的线索】
{revealed_text}

在场其他人的公开身份：
{other_chars_text}
可选的投票对象（格式：角色ID=姓名）：{candidates or '无'}

【讨论历史】（最新发言在最后）
{discussion_text}

{vote_task}"""

    @staticmethod
    def base_roleplay_template(
        character: "ScriptCharacter",
        case: Optional["CaseData"] = None,
    ) -> str:
        """Base template for roleplaying as a character.

        Args:
            character: The character being prompted.
            case: The case data (for the case block).

        Returns:
            The base system prompt.
        """
        return f"""{_case_block(case)}

身份：{character.public_identity}
用中文回复。"""