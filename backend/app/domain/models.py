# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Domain models for the murder mystery game."""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


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

    lead_title: Optional[str] = None
    """Player-facing title for the investigation direction that finds this clue."""

    lead_description: Optional[str] = None
    """Player-facing description of the investigation direction."""

    importance: str = "supporting"
    """Internal evidence weight: core, supporting, or red_herring."""

    reliability: float = 0.8
    """How trustworthy this clue is before cross-checking."""

    related_characters: list[str] = field(default_factory=list)
    """Character IDs connected to this clue."""

    related_time: str = ""
    """Optional time marker used by the evidence timeline."""

    relations: list[dict[str, str]] = field(default_factory=list)
    """Links to other clues: [{target_id, type, label}]."""


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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "topic": self.topic,
            "title": self.title,
            "case": asdict(self.case),
            "characters": [asdict(c) for c in self.characters],
            "clues": [asdict(c) for c in self.clues],
            "story_content": self.story_content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoryArchive":
        """Load from dictionary."""
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            topic=data["topic"],
            title=data["title"],
            case=CaseData(**data["case"]),
            characters=[ScriptCharacter(**c) for c in data["characters"]],
            clues=[ClueData(**c) for c in data["clues"]],
            story_content=data["story_content"],
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

    investigation_actions_remaining: Optional[int] = None
    """Remaining investigation actions in the current round.

    ``None`` keeps classic mode's existing unrestricted investigation behavior;
    quick mode uses one action per round.
    """

    min_investigation_rounds: int = 2
    """Minimum number of investigation rounds before voting"""

    player_states: dict[str, PlayerState] = field(default_factory=dict)
    """Player states keyed by player ID"""

    eliminated_id: Optional[str] = None
    """ID of the character who was eliminated"""

    votes_record: list[dict] = field(default_factory=list)
    """Vote records [{"player_id": "...", "target_id": "..."}]"""

    discussion_history: list[str] = field(default_factory=list)
    """Discussion history of all players' statements"""

    game_ended: bool = False
    """Whether the game has ended"""

    winner: Optional[str] = None
    """Winner: "good", "killer", or None"""

    reveal_triggered: bool = False
    """Whether the reveal phase has been triggered"""

    last_event: Optional[dict] = None
    """Latest gameplay beat shown to the player."""

    final_deduction: Optional[dict] = None
    """The player's sealed pre-vote deduction, if submitted."""


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
