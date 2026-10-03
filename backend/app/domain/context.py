"""Immutable dialogue records and the only data passed to roleplay workers."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class StatementClaim:
    text: str
    kind: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscussionEvent:
    event_id: str
    sequence: int
    speaker_id: str
    speaker_name: str
    text: str
    phase: str | None = None
    round: int | None = None
    action_id: str = ""
    kind: str = "statement"
    target_id: str | None = None
    audience: tuple[str, ...] = ()  # Empty means public.
    presented_clue_ids: tuple[str, ...] = ()
    reply_to: str | None = None
    claims: tuple[StatementClaim, ...] = ()
    corrections: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> "DiscussionEvent":
        values = dict(raw)
        for key in ("audience", "presented_clue_ids", "corrections"):
            values[key] = tuple(values.get(key, ()))
        values["claims"] = tuple(
            StatementClaim(c["text"], c["kind"], tuple(c.get("source_ids", ())))
            for c in values.get("claims", ())
        )
        return cls(**values)


@dataclass(frozen=True)
class ContextSource:
    source_id: str
    kind: str
    text: str
    speaker_id: str = ""


@dataclass(frozen=True)
class RoleContext:
    """Serialized values prevent shared mutable objects crossing threads."""

    payload_json: str
    sources: tuple[ContextSource, ...]
    stable_prefix: str = ""
    game_id: str = ""
    action_id: str = ""
    snapshot_seq: int = 0
    character_id: str = ""
    phase: str = ""
    round: int = 0
    candidate_ids: tuple[str, ...] = ()
    omitted_event_ids: tuple[str, ...] = ()
    estimated_tokens: int = 0

    def payload(self) -> dict:
        return json.loads(self.payload_json)

    @classmethod
    def from_dict(cls, raw: dict) -> 'RoleContext':
        values = dict(raw)
        values['sources'] = tuple(ContextSource(**s) for s in values['sources'])
        for name in ('candidate_ids', 'omitted_event_ids'):
            values[name] = tuple(values.get(name, ()))
        return cls(**values)

    def trace_metadata(self) -> dict:
        return {
            "game_id": self.game_id, "action_id": self.action_id,
            "snapshot_seq": self.snapshot_seq, "character_id": self.character_id,
            "phase": self.phase, "round": self.round, "context_version": 3,
            "context_profile": "public_intro" if self.phase == "introduction" else "private_role",
            "selected_source_ids": [s.source_id for s in self.sources],
            "omitted_event_ids": list(self.omitted_event_ids),
            "estimated_input_tokens": self.estimated_tokens,
        }


class CharacterReply(str):
    """Keep the public text API while carrying validated internal provenance."""

    def __new__(cls, speech: str, claims: tuple[StatementClaim, ...] = (),
                corrections: tuple[str, ...] = ()):
        reply = super().__new__(cls, speech)
        reply.claims = claims
        reply.corrections = corrections
        return reply
