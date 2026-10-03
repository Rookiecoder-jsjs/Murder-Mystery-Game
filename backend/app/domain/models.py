# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Domain models for the murder mystery game."""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

from app.domain.context import DiscussionEvent


class ClueStatus(Enum):
    """Clue status."""

    OWNED = "owned"
    AVAILABLE = "available"
    SCENE_PUBLIC = "scene_public"


@dataclass
class CaseData:
    """Case information."""

    title: str
    """Case name"""

    background: str
    """Story background"""

    victim: str
    """Victim name"""

    crime: str
    """Crime description"""

    true_killer: str
    """The real killer's character ID"""

    motive: str
    """Killer's motive"""

    location: str = ""
    """Location"""

    time: str = ""
    """Time"""


@dataclass
class ClueData:
    """Clue information."""

    id: str
    """Unique clue ID"""

    content: str
    """Clue content"""

    type: str
    """Clue type: physical, testimony, document"""

    holder_id: str
    """ID of the character who holds this clue, or 'scene' for scene clues"""

    reveal_to_all: bool = False
    """Whether this clue has been revealed to all players"""

    required_clue_id: Optional[str] = None
    """ID of another clue that must be obtained first to unlock this one"""

    discovery_round: int = 0
    """Quick-mode release round (1-3); 0 schedules legacy clues automatically."""

    lead: str = ""
    """Spoiler-free place or object the player may choose to investigate."""


@dataclass
class ScriptCharacter:
    """Murder mystery character."""

    id: str
    """Unique character ID (e.g., 'char_1')"""

    name: str
    """Character name"""

    public_identity: str
    """Public identity shown to other players"""

    secret: str
    """Hidden secret that the character tries to conceal"""

    is_killer: bool = False
    """Whether this character is the killer"""

    clues: list[str] = field(default_factory=list)
    """IDs of clues held by this character"""

    alibi: str = ""
    """Character's alibi"""

    dialogue_style: str = ""
    """Character's speaking style"""

    backstory: str = ""
    """Character's background story"""

    relationship_with_victim: str = ""
    """Relationship with the victim"""

    motive: str = ""
    """Killer's motive (only for killer)"""

    appearance: str = ""
    """Physical appearance"""

    portrait_url: str = ""
    """Stable local URL of the generated portrait"""

    self_knowledge: str = ""
    """First-person knowledge only; never copy omniscient author notes here."""

    objectives: list[str] = field(default_factory=list)
    """Roleplay goals, separate from the final culprit verdict."""

    cover_story: str = ""
    """Explicit authored cover story, never treated as personal fact."""

    public_introduction: str = ""
    """Prepared public introduction; legacy archives use name and identity."""

    def role_script(self) -> str:
        """Use reviewed knowledge, with a non-spoiling legacy fallback."""
        knowledge = self.self_knowledge or (
            f"你的公开身份：{self.public_identity}。旧版剧本未提供个人经历，"
            "请依据已获得的线索调查，不要把未知事实当作亲历。"
        )
        return knowledge + (f"\n【对外说辞（并非事实）】\n{self.cover_story}" if self.cover_story else "")


@dataclass
class StoryArchive:
    """Story archive - complete story that can be loaded multiple times."""

    id: str
    """UUID, used as filename"""

    created_at: str
    """Creation timestamp"""

    topic: str
    """Original topic"""

    title: str
    """Story title"""

    case: CaseData
    """Case information (includes truth)"""

    characters: list[ScriptCharacter]
    """All characters (includes hidden identities)"""

    clues: list[ClueData]
    """All clues"""

    story_content: str
    """Complete story text (background, relationships, truth)"""

    solution: list[dict] = field(default_factory=list)
    """Author-only deductions with exact supporting clue quotations."""

    production: dict = field(default_factory=dict)
    """Persisted authoring result; absent for already saved legacy stories."""

    catalog: dict = field(default_factory=dict)
    """Public package metadata, frozen with the archive in each game snapshot."""

    def __post_init__(self) -> None:
        """Normalize holder_id drift at the archive boundary.

        LLM generation sometimes emits scene variants like ``"scene_01"``
        instead of the exact ``"scene"`` literal — left as-is they slip
        past the scene-clue reveal/reserve logic (which matches the
        literal) and leak scene clues as private AI knowledge. Anything
        that is neither ``"scene"`` nor a known character ID is treated
        as scene-held.
        """
        if not self.characters:
            return
        char_ids = {c.id for c in self.characters}
        for clue in self.clues:
            if clue.holder_id != "scene" and clue.holder_id not in char_ids:
                clue.holder_id = "scene"
        # The case's culprit ID is the authoritative truth, not an LLM flag.
        for character in self.characters:
            character.is_killer = character.id == self.case.true_killer

    def validate(self, require_script: bool = False, require_solution: bool = False) -> None:
        """Reject broken references and unreachable evidence before play."""
        if not isinstance(self.production, dict):
            raise ValueError("剧本制作记录格式错误")
        if not isinstance(self.catalog, dict):
            raise ValueError("剧本目录信息格式错误")
        char_ids = [c.id for c in self.characters]
        clue_ids = [c.id for c in self.clues]
        if len(char_ids) != len(set(char_ids)) or len(clue_ids) != len(set(clue_ids)):
            raise ValueError("角色或线索 ID 重复")
        if len(self.characters) < 2 or self.case.true_killer not in char_ids:
            raise ValueError("真凶不存在或缺少可供玩家扮演的角色")
        if len({c.name for c in self.characters}) != len(self.characters):
            raise ValueError("角色姓名重复，无法指认")
        clues_by_id = {c.id: c for c in self.clues}
        for character in self.characters:
            if not isinstance(character.self_knowledge, str) or not isinstance(character.objectives, list):
                raise ValueError("角色本人知识或任务格式错误")
            if any(not isinstance(goal, str) for goal in character.objectives):
                raise ValueError("角色任务必须为文本")
            if not isinstance(character.cover_story, str):
                raise ValueError("对外说辞必须为文本")
            if not isinstance(character.public_introduction, str):
                raise ValueError("公开介绍必须为文本")
            if any(cid not in clue_ids for cid in character.clues):
                raise ValueError("角色持有的线索不存在")
            wrong_holders = [f"{cid}(holder_id={clues_by_id[cid].holder_id})"
                             for cid in character.clues if clues_by_id[cid].holder_id != character.id]
            if wrong_holders:
                raise ValueError(
                    f"角色初始线索归属错误：{character.id}.clue_ids 引用了 {'、'.join(wrong_holders)}。"
                    f"clue_ids 只能列 holder_id={character.id} 的线索；请移除场景或他人的线索引用，"
                    "不要为绕过校验改变线索归属。相关亲历信息可写入 self_knowledge。"
                )
            if require_script and (not character.self_knowledge.strip() or not character.objectives):
                missing = [field for field, present in (
                    ('self_knowledge', character.self_knowledge.strip()),
                    ('objectives', character.objectives),
                ) if not present]
                raise ValueError(
                    f"新剧本必须提供角色本人知识和任务：{character.id} 缺少 {'、'.join(missing)}；"
                    "请检查并补齐每个角色对应字段，只能写本人亲历的知识。"
                )
        for clue in self.clues:
            if not isinstance(clue.content, str) or not clue.content.strip():
                raise ValueError("线索内容不能为空")
            if clue.required_clue_id and clue.required_clue_id not in clue_ids:
                raise ValueError("线索前置不存在")
            if type(clue.discovery_round) is not int or not 0 <= clue.discovery_round <= 3:
                raise ValueError("调查轮次必须为 1-3（旧版缺省为 0）")
            if require_script and (not clue.discovery_round or not isinstance(clue.lead, str) or not clue.lead.strip()):
                raise ValueError("新剧本必须提供调查轮次与方向")
            dependency = clues_by_id.get(clue.required_clue_id)
            if dependency and clue.discovery_round and dependency.discovery_round > clue.discovery_round:
                raise ValueError("前置线索不能晚于后续线索")
        if require_script and {c.discovery_round for c in self.clues} != {1, 2, 3}:
            raise ValueError("新剧本必须在三轮都提供证据")
        self.ordered_clues()
        if not isinstance(self.solution, list) or (require_solution and not self.solution):
            raise ValueError("新剧本必须提供结论与证据的对应关系 solution")
        for deduction_index, deduction in enumerate(self.solution):
            if (not isinstance(deduction, dict) or set(deduction) != {"conclusion", "evidence"}
                    or not isinstance(deduction["conclusion"], str) or not deduction["conclusion"].strip()
                    or not isinstance(deduction["evidence"], list) or not deduction["evidence"]):
                raise ValueError("结论必须有可调查的证据")
            for reference_index, reference in enumerate(deduction["evidence"]):
                if not isinstance(reference, dict) or set(reference) != {"clue_id", "quote"}:
                    raise ValueError("结论证据引用格式错误")
                clue = clues_by_id.get(reference["clue_id"]) if isinstance(reference["clue_id"], str) else None
                quote = reference["quote"]
                if not clue or not isinstance(quote, str) or not quote.strip() or quote not in clue.content:
                    raise ValueError(
                        f"solution[{deduction_index}].evidence[{reference_index}] 结论引用了不存在的线索或原文："
                        f"clue_id={reference['clue_id']}，quote={str(quote)[:160]}；"
                        "请从对应 clues.content 逐字复制完整依据，不要改写原文。"
                    )

    def ordered_clues(self) -> list[ClueData]:
        """Stable topological order; cycles must never silently hide clues."""
        ordered: list[ClueData] = []
        remaining = list(self.clues)
        reached: set[str] = set()
        while remaining:
            ready = [c for c in remaining if not c.required_clue_id or c.required_clue_id in reached]
            if not ready:
                raise ValueError("线索依赖存在循环，无法完成调查")
            ordered.extend(ready)
            reached.update(c.id for c in ready)
            remaining = [c for c in remaining if c.id not in reached]
        return ordered

    def release_rounds(self) -> dict[str, int]:
        """Schedule legacy evidence evenly, never before its prerequisite."""
        ordered = self.ordered_clues()
        rounds: dict[str, int] = {}
        for index, clue in enumerate(ordered):
            proposed = clue.discovery_round or min(3, index * 3 // max(1, len(ordered)) + 1)
            rounds[clue.id] = max(proposed, rounds.get(clue.required_clue_id, 1))
        return rounds

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        ``reveal_to_all`` is pinned to ``False``: which clues are public is
        per-game runtime state (owned by the session snapshot's
        ``revealed_clue_ids``), never part of the archive. Serializing the
        live flag leaked a playthrough into the story file — the portrait
        thread re-saves this archive while the game that shares it is
        already revealing scene clues.
        """
        return {
            "id": self.id,
            "created_at": self.created_at,
            "topic": self.topic,
            "title": self.title,
            "case": asdict(self.case),
            "characters": [asdict(c) for c in self.characters],
            "clues": [{**asdict(c), "reveal_to_all": False} for c in self.clues],
            "story_content": self.story_content,
            "solution": self.solution,
            "production": self.production,
            "catalog": self.catalog,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoryArchive":
        """Load from dictionary.

        Mirrors ``to_dict``: any ``reveal_to_all`` stored in the file is
        discarded, so archives written before the flag was pinned heal on
        load instead of starting a game pre-revealed.
        """
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            topic=data["topic"],
            title=data["title"],
            case=CaseData(**data["case"]),
            characters=[ScriptCharacter(**c) for c in data["characters"]],
            clues=[
                ClueData(**{**c, "reveal_to_all": False})
                for c in data["clues"]
            ],
            story_content=data["story_content"],
            solution=data.get("solution", []),
            production=data.get("production", {}),
            catalog=data.get("catalog", {}),
        )

    @staticmethod
    def generate_id() -> str:
        """Generate a new archive ID."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_timestamp() -> str:
        """Generate a timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class PlayerState:
    """Player state during the game."""

    character_id: str
    """The character ID this player is playing"""

    is_alive: bool = True
    """Whether the player is still in the game"""

    accusation_points: int = 1
    """Number of times this player can accuse (once per game)"""

    known_clues: list[str] = field(default_factory=list)
    """IDs of clues this player has obtained"""

    has_accused: bool = False
    """Whether this player has already accused someone"""

    vote: Optional[str] = None
    """Current vote target (character ID)"""


@dataclass
class GameState:
    """Game state."""

    story_id: str
    """Story ID"""

    mode: str = "classic"
    """Game mode: ``classic`` or the shorter ``quick`` mode."""

    phase: str = "introduction"
    """Current phase"""

    turn: int = 0
    """Current turn within the phase"""

    round: int = 1
    """Current discussion round"""

    max_rounds: int = 5
    """Maximum number of discussion rounds"""

    investigation_count: int = 0
    """Number of times investigation has been done"""

    investigated_round: int = 0
    """Latest quick-mode round investigated by the human player."""

    discussed_round: int = 0
    """Latest quick-mode round with a completed human discussion."""

    min_investigation_rounds: int = 2
    """Minimum number of investigation rounds before voting"""

    player_states: dict[str, PlayerState] = field(default_factory=dict)
    """Player states keyed by player ID"""

    eliminated_id: Optional[str] = None
    """ID of the character who was eliminated"""

    votes_record: list[dict] = field(default_factory=list)
    """Vote records [{"player_id": "...", "target_id": "..."}]"""

    ballot_details: list[dict] = field(default_factory=list)
    """Final NPC advice, including abstentions, persisted for the reveal."""

    discussion_history: list[str] = field(default_factory=list)
    """Legacy public-text projection; discussion_events is authoritative."""

    discussion_events: list[DiscussionEvent] = field(default_factory=list)
    """Append-only testimony, never an update to authored case facts."""

    game_ended: bool = False
    """Whether the game has ended"""

    winner: Optional[str] = None
    """Winner: "good", "killer", or None"""

    reveal_triggered: bool = False
    """Whether the reveal phase has been triggered"""

    last_event: Optional[dict] = None
    """Latest gameplay beat shown to the player."""


@dataclass
class ClueBoardEntry:
    """One entry on the clue board."""

    clue: ClueData
    status: str  # "owned", "available", "scene_public"


@dataclass
class ClueBoard:
    """Clue board showing all clues and their status."""

    owned: tuple[ClueBoardEntry, ...] = field(default_factory=tuple)
    available: tuple[ClueBoardEntry, ...] = field(default_factory=tuple)
    scene_public: tuple[ClueBoardEntry, ...] = field(default_factory=tuple)
