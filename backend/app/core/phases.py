# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Game phase definitions for the murder mystery game."""

from enum import Enum


class GamePhase(Enum):
    """Murder mystery game phases."""

    INTRODUCTION = "introduction"
    """自我介绍阶段 - 玩家和AI角色介绍自己的公开身份"""

    INVESTIGATION = "investigation"
    """搜证阶段 - 玩家可以获取线索"""

    DISCUSSION = "discussion"
    """讨论阶段 - 玩家和AI角色讨论案情"""

    VOTING = "voting"
    """投票阶段 - 玩家投票指认凶手"""

    REVEAL = "reveal"
    """真相揭晓阶段 - 公布真相和游戏结果"""


PHASE_SEQUENCE = [
    GamePhase.INTRODUCTION,
    GamePhase.INVESTIGATION,
    GamePhase.DISCUSSION,
    GamePhase.VOTING,
    GamePhase.REVEAL,
]
"""所有阶段的顺序"""


def next_phase(current: GamePhase) -> GamePhase:
    """Get the next phase after the current one.

    Args:
        current: The current game phase.

    Returns:
        The next phase in the sequence.
    """
    try:
        current_index = PHASE_SEQUENCE.index(current)
        next_index = current_index + 1
        if next_index < len(PHASE_SEQUENCE):
            return PHASE_SEQUENCE[next_index]
        return current
    except ValueError:
        return current


def is_valid_phase(phase_name: str) -> bool:
    """Check if a phase name is valid.

    Args:
        phase_name: The phase name to check.

    Returns:
        True if valid, False otherwise.
    """
    return phase_name in [p.value for p in GamePhase]


GamePhase.next = classmethod(lambda cls, current: next_phase(current))
GamePhase.is_valid_phase = classmethod(lambda cls, name: is_valid_phase(name))
