"""Build a role's allowed view, then select source-preserving dialogue memory."""

import json
import re

from app.core.phases import GamePhase
from app.core.prompts import PhasePromptTemplates
from app.core.roleplay_protocol import statement_tool_spec, vote_tool_spec
from app.domain.context import ContextSource, DiscussionEvent, RoleContext
from app.domain.models import CaseData, ClueData, ScriptCharacter


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def estimate_tokens(text: str) -> int:
    """Conservative UTF-8 estimate, not a provider-specific tokenizer."""
    return (len(text.encode("utf-8")) + 1) // 2


class ContextBudgetExceeded(ValueError):
    pass


class ContextAssembler:
    """No full archive/state survives into the immutable result."""

    @staticmethod
    def assemble(
        *, character: ScriptCharacter, phase: GamePhase, case: CaseData | None,
        known_clues: list[ClueData] = (), revealed_clues: list[ClueData] = (),
        other_chars: list[ScriptCharacter] = (), events: tuple[DiscussionEvent, ...] = (),
        user_input: str = "", user_persona: str = "", game_id: str = "",
        action_id: str = "", snapshot_seq: int = 0, round: int = 0,
        current_event_id: str = "", token_budget: int = 12000,
    ) -> RoleContext:
        sources: list[ContextSource] = []

        def source(source_id: str, kind: str, text: str) -> dict:
            sources.append(ContextSource(source_id, kind, text))
            return {"source_id": source_id, "kind": kind, "text": text}

        intro = phase == GamePhase.INTRODUCTION
        role = {
            "id": character.id, "name": character.name,
            "identity": source("role:public", "identity", character.public_identity),
            "appearance": character.appearance, "style": character.dialogue_style,
        }
        if not intro:
            # Legacy prose mixed truth and cover in the same paragraph. Keep
            # that material available as a report, never certify it as fact.
            knowledge = character.self_knowledge or character.role_script()
            legacy_notes = []
            if not character.cover_story:
                sections = re.split(r"(?=【)", knowledge)
                legacy_notes = [s for s in sections if re.match(r"【[^】]*(?:对外说辞|掩饰)[^】]*】", s)]
                knowledge = "".join(s for s in sections if s not in legacy_notes)
            role.update({
                "is_killer": character.is_killer,
                "can_use_cover": bool(character.cover_story),
                "personal_knowledge": source("self:knowledge", "personal", knowledge),
                "objectives": list(character.objectives),
            })
            if character.cover_story:
                role["cover_story"] = source("self:cover", "cover", character.cover_story)
            if legacy_notes:
                role["legacy_alibi"] = source("self:legacy_alibi", "document", "\n".join(legacy_notes))
        public_case = {
            field: source(f"case:{field}", "case", getattr(case, field))
            for field in ("title", "time", "location", "background", "victim", "crime")
            if case and getattr(case, field)
        }
        public_ids = {c.id for c in revealed_clues}
        visible_clues = {c.id: c for c in (*known_clues, *revealed_clues)} if not intro else {}
        clues = []
        for clue in sorted(visible_clues.values(), key=lambda c: c.id):
            item = source(f"clue:{clue.id}", clue.type, clue.content)
            item.update({"id": clue.id, "type": clue.type, "holder_id": clue.holder_id,
                         "meaning": "物证记载" if clue.type == "physical" else "内容为待核实的记载或证言"})
            clues.append(item)
        peers = [{"id": c.id, "name": c.name,
                  **source(f"character:{c.id}", "identity", c.public_identity)}
                 for c in sorted(other_chars, key=lambda c: c.id) if c.id != character.id]
        candidates = tuple(c["id"] for c in peers) if phase == GamePhase.VOTING else ()
        # Ordered serialization is part of the cache contract: common case,
        # private role, evidence, chronological quotes, then volatile action.
        # Never add action/game IDs, phase, clocks or retrieval scores here.
        fixed = {"version": 3, "case": public_case, "role": role,
                 "player": user_persona, "characters": peers}
        stable_prefix = encode(fixed)[:-1]  # Actual leading bytes of payload_json.
        payload = {
            **fixed, "clues": clues, "testimony": [],
            "phase": phase.value, "round": round, "candidates": list(candidates),
            "public_clue_ids": sorted(public_ids & visible_clues.keys()),
            "presented_clue_ids": [cid for e in events if e.event_id == current_event_id
                                   for cid in e.presented_clue_ids if cid in visible_clues],
            "allowed_source_ids": [s.source_id for s in sources],
            "allowed_correction_ids": [],
        }
        fixed_source_ids = [s.source_id for s in sources]
        tools = [vote_tool_spec()] if phase == GamePhase.VOTING else [statement_tool_spec()]

        def cost() -> int:
            messages = PhasePromptTemplates.messages(encode(payload), user_input, phase)
            # Reserve repair instructions and provider message framing.
            return estimate_tokens(encode({"messages": messages, "tools": tools})) + 1024

        if cost() > token_budget:
            raise ContextBudgetExceeded("必要案情、本人知识和线索超过上下文预算，请提高 ROLEPLAY_CONTEXT_TOKEN_BUDGET")

        # ACL before ranking, including legacy private memories and corrections.
        allowed = sorted((e for e in events if (not e.audience or character.id in e.audience)
                          and e.event_id != current_event_id and e.kind != "delivery_error"),
                         key=lambda e: (e.sequence, e.event_id)) if not intro else []
        recent_ids = {e.event_id for e in allowed[-8:]}
        query = user_input + " ".join(c.content for c in revealed_clues if c.id in
                                    {cid for e in events if e.event_id == current_event_id
                                     for cid in e.presented_clue_ids})
        terms = set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2}", query))

        def score(event: DiscussionEvent) -> tuple[int, int]:
            relevance = sum(1 for term in terms if term in event.text)
            key = bool(event.claims or event.presented_clue_ids or re.search(
                r"\d{1,2}[:：]\d{2}|[一二三四五六七八九十]+[点时]|不在场|承认|隐瞒|目击|看见|更正|说错|矛盾", event.text))
            return (relevance * 6 + key * 12 + bool(event.corrections) * 20
                    + (event.speaker_id == character.id) * 4
                    + (event.event_id in recent_ids) * 8, event.sequence)

        selected: dict[str, DiscussionEvent] = {}
        by_id = {e.event_id: e for e in allowed}

        def event_view(e: DiscussionEvent) -> dict:
            return {"source_id": f"event:{e.event_id}", "event_id": e.event_id,
                    "speaker_id": e.speaker_id, "speaker": e.speaker_name,
                    "phase": e.phase, "round": e.round, "quote": e.text,
                    "status": "未经证实的发言", "corrections": [i for i in e.corrections if i in by_id],
                    "presented_clue_ids": [i for i in e.presented_clue_ids if i in visible_clues]}

        def render() -> None:
            ordered = sorted(selected.values(), key=lambda e: (e.sequence, e.event_id))
            # Age affects retrieval only. Moving quotes between recent/old
            # sections would rewrite the prefix on every ninth utterance.
            payload["testimony"] = [event_view(e) for e in ordered]
            payload["allowed_source_ids"] = fixed_source_ids + [f"event:{e.event_id}" for e in ordered]
            payload["allowed_correction_ids"] = [e.event_id for e in ordered if e.speaker_id == character.id]

        # Most games fit in full. Avoid re-ranking/re-serializing every event
        # when no compaction is needed; this also preserves append-only history.
        selected.update(by_id)
        render()
        fits_all = cost() <= token_budget
        if not fits_all:
            selected.clear()
            render()
        # Keep corrections together with their original utterance, never a free
        # summary that can promote a speaker's claim into a world fact.
        for event in ([] if fits_all else sorted(allowed, key=score, reverse=True)):
            bundle: dict[str, DiscussionEvent] = {}

            def collect(e: DiscussionEvent) -> None:
                if e.event_id in bundle or e.event_id in selected:
                    return
                bundle[e.event_id] = e
                for original in e.corrections:
                    if original in by_id:
                        collect(by_id[original])

            collect(event)
            selected.update(bundle)
            render()
            if cost() > token_budget:
                for event_id in bundle:
                    selected.pop(event_id)
                render()
        for event in sorted(selected.values(), key=lambda e: e.sequence):
            sources.append(ContextSource(f"event:{event.event_id}", "testimony", event.text, event.speaker_id))
        return RoleContext(
            payload_json=encode(payload), sources=tuple(sources), stable_prefix=stable_prefix, game_id=game_id,
            action_id=action_id, snapshot_seq=snapshot_seq, character_id=character.id,
            phase=phase.value, round=round, candidate_ids=candidates,
            omitted_event_ids=tuple(e.event_id for e in allowed if e.event_id not in selected),
            estimated_tokens=cost(),
        )
