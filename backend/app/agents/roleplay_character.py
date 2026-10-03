# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Character roleplay implementation using the OpenAI client directly.

Defaults to DeepSeek V4 Flash with thinking mode disabled — discussion
rounds fire all characters concurrently and want low latency, not deep
reasoning.

Context assembly uses immutable, permission-filtered views and source-backed
utterances. Session events are authoritative; legacy standalone callers can
still pass discussion lines. Model output is validated before it is published.
"""

import json
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from openai import OpenAI
    from app.domain.models import CaseData

from app.core.config import RoleplayConfig, get_config
from app.core.errors import ModelInterrupted
from app.core.llm_trace import trace_llm_chat
from app.core.logging import get_logger
from app.core.phases import GamePhase
from app.core.prompts import PhasePromptTemplates
from app.core.prompt_cache import prefix_fingerprint
from app.domain.models import ScriptCharacter, ClueData
from app.domain.context import DiscussionEvent, RoleContext, CharacterReply, StatementClaim
from app.core.roleplay_protocol import (
    statement_tool_spec, vote_tool_spec, validate_statement, InvalidStatement,
    review_tool_spec, REVIEW_RULES, speech_segments, speech_sentence_contexts,
    canonical_statement, narrow_statement_sources, is_record_description,
)
from app.services.context_service import ContextAssembler, ContextBudgetExceeded, encode, estimate_tokens


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

    def _legacy_context(
        self, user_input: str, phase: GamePhase, case,
        known_clues, revealed_clues, other_chars, discussion_history,
    ) -> RoleContext:
        """Adapter for CLI callers; shared history takes precedence over memory."""
        lines = list(discussion_history or [])
        # Older callers already append the current user question to the log.
        if user_input and lines and lines[-1].partition(": ")[2] == user_input:
            lines.pop()
        events = []
        names = {c.name: c.id for c in [self.character, *other_chars]}
        for index, line in enumerate(lines, 1):
            name, separator, text = line.partition(": ")
            events.append(DiscussionEvent(
                f"legacy{index}", index, names.get(name, ""), name if separator else "未知",
                text if separator else line, kind="legacy_statement",
            ))
        if not discussion_history:
            for entry in self.conversation_history:
                own = entry["role"] == "assistant"
                index = len(events) + 1
                events.append(DiscussionEvent(
                    f"legacy{index}", index, self.character_id if own else "",
                    self.name if own else self.user_persona, entry["message"], kind="legacy_statement",
                ))
        return ContextAssembler.assemble(
            character=self.character, phase=phase, case=case,
            known_clues=known_clues, revealed_clues=revealed_clues,
            other_chars=other_chars, events=tuple(events), user_input=user_input,
            user_persona=self.user_persona, token_budget=self.config.context_token_budget,
        )

    def _build_messages(
        self, user_input: str, phase: GamePhase, case=None,
        known_clues=None, revealed_clues=None, other_chars=None, discussion_history=None,
        context: RoleContext | None = None,
    ) -> List[Dict[str, str]]:
        """Rules, quoted context and the current action each have one place."""
        context = context or self._legacy_context(
            user_input, phase, case if case is not None else self.case,
            known_clues or [], revealed_clues or [], other_chars or [], discussion_history or [],
        )
        if context.character_id != self.character_id or context.phase != phase.value:
            raise ValueError("角色上下文与当前请求不匹配")
        return PhasePromptTemplates.messages(context.payload_json, user_input, phase)

    def _create_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        thinking_enabled: Optional[bool] = None,
        temperature: float | None = None,
        model_name: str | None = None,
        max_tokens: int | None = None,
    ):
        """Call the chat completion API with roleplay generation params.

        Thinking mode is toggled per ``config.thinking_enabled`` — it is
        off by default so concurrent replies stay fast. Note that with
        thinking enabled the API silently ignores temperature/top_p. A
        ``thinking_enabled`` override (votes always disable it) wins.
        """
        if thinking_enabled is None:
            thinking_enabled = self.config.thinking_enabled
        return self.client.chat.completions.create(
            model=model_name or self.config.model_name,
            messages=messages,
            temperature=self.config.generation.temperature if temperature is None else temperature,
            top_p=self.config.generation.top_p,
            max_tokens=max_tokens or self.config.generation.max_completion_tokens,
            tools=tools,
            tool_choice=tool_choice,
            extra_body={
                "thinking": {
                    "type": "enabled" if thinking_enabled else "disabled"
                }
            },
        )

    def _call_with_trace(
        self,
        messages: List[Dict[str, str]],
        *,
        trace_context: Dict[str, Any],
        cache_prefix: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        thinking_enabled: Optional[bool] = None,
        temperature: float | None = None,
        model_name: str | None = None,
        max_tokens: int | None = None,
    ):
        """Run one completion and record it to the JSONL LLM trace.

        On success the ``response`` trace field carries the text reply or —
        when the model returns a tool call instead — a compact rendering of
        that call. On error the failure is traced and re-raised so each
        caller keeps its own fallback semantics.
        """
        trace_context = {"stage": "generation", **trace_context}
        model_name = model_name or self.config.model_name
        if cache_prefix:
            trace_context["cache_prefix_sha256"] = prefix_fingerprint(
                model=model_name, system=messages[0]["content"], context_prefix=cache_prefix,
                tools=tools, tool_choice=tool_choice,
                thinking=self.config.thinking_enabled if thinking_enabled is None else thinking_enabled,
            )
        start = time.monotonic()
        try:
            response = self._create_completion(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                thinking_enabled=thinking_enabled,
                temperature=temperature,
                model_name=model_name,
                max_tokens=max_tokens,
            )
        except ModelInterrupted:
            raise
        except Exception as e:
            trace_llm_chat(
                model=model_name,
                kind="roleplay",
                messages=messages,
                context=trace_context,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
            raise

        message = response.choices[0].message
        content = message.content
        tool_calls = getattr(message, "tool_calls", None)
        if content:
            trace_body = content
        elif tool_calls:
            trace_body = json.dumps(
                [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in tool_calls
                ],
                ensure_ascii=False,
            )
        else:
            trace_body = ""
        trace_llm_chat(
            model=model_name,
            kind="roleplay",
            messages=messages,
            context=trace_context,
            response=trace_body,
            reasoning=getattr(message, "reasoning_content", "") or "",
            usage=getattr(response, "usage", None),
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return message

    def respond(
        self, user_input: str, phase: GamePhase,
        known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
        discussion_history: Optional[List[str]] = None,
        case: Optional["CaseData"] = None, record_in_memory: bool = True,
        context: RoleContext | None = None,
    ) -> str:
        """Generate, validate and retry once before publishing a statement."""
        session_context = context is not None
        try:
            context = context or self._legacy_context(
                user_input, phase, case if case is not None else self.case,
                known_clues or [], revealed_clues or [], other_chars or [], discussion_history or [],
            )
            messages = self._build_messages(user_input, phase, context=context)
        except ContextBudgetExceeded:
            return CharacterReply("这次需要核对的资料过多，我暂时无法完成判断。")
        if phase == GamePhase.INTRODUCTION:
            # Identity is authored data; generating extra biography here has
            # no gameplay value and used to bypass the semantic validator.
            identity = context.payload()["role"]["identity"]["text"]
            speech = f"我是{self.name}，{identity}。"
            return CharacterReply(speech, (StatementClaim(identity, "observed", ("role:public",)),))
        trace_context = {**context.trace_metadata(), "character_name": self.name}
        reply = self._clarification(context, user_input)
        for attempt in range(2):
            raw = ""
            try:
                message = self._call_with_trace(
                    messages, trace_context={**trace_context, "attempt": attempt + 1},
                    cache_prefix=context.stable_prefix, tools=[statement_tool_spec()],
                    tool_choice={"type": "function", "function": {"name": "submit_statement"}},
                    model_name=(self.config.review_model_name or self.config.model_name) if attempt else None,
                    temperature=0 if attempt else None,
                )
                calls = [tc for tc in (getattr(message, "tool_calls", None) or [])
                         if tc.function.name == "submit_statement"]
                if len(calls) != 1:
                    raise InvalidStatement("必须调用一次 submit_statement 提交发言和来源")
                raw = narrow_statement_sources(canonical_statement(calls[0].function.arguments), context)
                result = validate_statement(raw, context)
                verified_claims = self._review_statement(raw, context, attempt + 1)
                reply = CharacterReply(self._strip_self_prefix(result), verified_claims, result.corrections)
                break
            except InvalidStatement as exc:
                logger.warning("角色 %s 发言校验未通过（第 %s 次）: %s", self.name, attempt + 1, exc)
                # A bounded repair draft is explicitly untrusted data, never
                # an accepted event or a second character memory.
                messages = messages[:3] + [{"role": "user", "content": encode({
                    "task": "修复未通过的草稿：只依据原始资料，删除无依据的分句，纠正类别及引用，150字内。"
                            "优先回答当前质问和出示证据，不重复旧说辞或无关秘密。纯粹未知用 aside；"
                            "‘我没离开’‘我没看见’等本人经历须用 observed 和本人原文，不能藏入 aside。"
                            "未知与事实分成完整句，别把半个问句独立提交。"
                            "rejected_draft 不是事实或历史，不能用它支持新发言。",
                    "validation_error": str(exc), "rejected_draft": raw[:4000],
                })}]
            except ModelInterrupted:
                raise
            except Exception as exc:
                logger.error("[Roleplay Error] %s: %s", self.name, exc)
                return "[回复失败]"
        # Only standalone callers use this compatibility buffer. Game sessions
        # persist the accepted reply once in their canonical event log.
        if record_in_memory and not session_context:
            if user_input:
                self.conversation_history.append({"role": "user", "message": user_input})
            self.conversation_history.append({"role": "assistant", "message": str(reply)})
        return reply

    @staticmethod
    def _clarification(context: RoleContext, question: str = "") -> CharacterReply:
        """Use relevant authored knowledge when repair fails, never the bad draft."""
        payload = context.payload()
        exhibit = next((c for c in payload["clues"]
                        if c["id"] in payload["presented_clue_ids"] and len(c["text"]) <= 500), None)
        claims = []
        parts = []
        if exhibit:
            quote = f"你出示的线索记载：「{exhibit['text']}」"
            parts.append(quote)
            claims.append(StatementClaim(quote, "reported", (exhibit["source_id"],)))
        source_id = "self:cover" if payload["role"].get("is_killer") else "self:knowledge"
        source = next((s for s in context.sources if s.source_id == source_id), None)
        # Match the question itself. A long exhibit often shares a generic
        # word (e.g. 时间) with an unrelated secret and used to dominate ranking.
        terms = set(re.findall(r"(?=([\u4e00-\u9fff]{2}))", question)) - {
            "什么", "为何", "为什么", "是否", "你说", "这个", "那个", "时间", "时候", "当时", "证据", "线索",
        }
        if source and terms:
            separator = r"[。；\n]" if source.kind == "cover" else r"[。\n]"
            sentences = [s.strip() for s in re.split(separator, re.sub(r"【[^】]*】", "", source.text))
                         if s.strip() and len(s.strip()) <= 160]
            sentence = max(sentences, key=lambda s: sum(t in s for t in terms), default="")
            if sentence and any(t in sentence for t in terms):
                if question and not exhibit:
                    # A directly authored first-person sentence answers the
                    # question without reprinting an entire exhibit. Do not
                    # paraphrase or retain anything from rejected model drafts.
                    speech = sentence + "。"
                    return CharacterReply(speech, (StatementClaim(
                        speech, "cover" if source.kind == "cover" else "observed", (source_id,)),))
                # When faced with evidence, a failed repair must not replace
                # the answer with the killer's stock alibi or another secret.
                # Keep the exhibit attributed and admit the explanation failed.
        parts.append("其余细节我无法确认。" if parts else "这部分我无法确认，请先核对已经出示的证据。")
        return CharacterReply("".join(parts), tuple(claims))

    def _review_statement(self, raw: str, context: RoleContext, attempt: int) -> tuple[StatementClaim, ...]:
        """An independent bounded semantic pass, using only this role's view."""
        draft = json.loads(raw)
        cited = {i for c in draft["claims"] for i in c["source_ids"]}
        # Never let unrelated past dialogue reinforce an invented personal memory.
        # Reported claims get their cited quotation; fact checks get authored
        # knowledge and evidence only. Voting may compare the available reports.
        facts = [s for s in context.sources if s.kind in {"case", "personal", "physical", "identity"}]
        covers = [s for s in context.sources if s.kind == "cover"]
        reports = [s for s in context.sources if s.kind not in {"case", "personal", "physical", "identity", "cover"}
                   and (s.source_id in cited or context.phase == GamePhase.VOTING.value)]
        # Public case first, private role next; evidence and draft remain at
        # the tail. No prior draft is retained between calls or after restore.
        fixed_facts = sorted((s for s in facts if not s.source_id.startswith("clue:")),
                             key=lambda s: (not s.source_id.startswith("case:"), s.source_id))
        fixed = {
            "version": 3,
            "facts": [{"source_id": s.source_id, "kind": s.kind, "text": s.text} for s in fixed_facts],
            "role": {"id": context.character_id, "is_killer": context.payload()["role"].get("is_killer", False),
                     "can_use_cover": context.payload()["role"].get("can_use_cover", False)},
            "authorized_covers": [{"source_id": s.source_id, "kind": s.kind, "text": s.text} for s in covers],
        }
        review_data = {
            **fixed,
            "evidence_facts": [{"source_id": s.source_id, "kind": s.kind, "text": s.text}
                               for s in sorted(facts, key=lambda s: s.source_id) if s.source_id.startswith("clue:")],
            "reports": [{"source_id": s.source_id, "kind": s.kind, "speaker_id": s.speaker_id,
                         "text": s.text, "status": "仅可归因引用，未经证实"} for s in reports],
            "mode": "vote" if context.phase == GamePhase.VOTING.value else "statement",
            "draft": draft,
            "speech_segments": speech_segments(draft["speech"]) if context.phase != GamePhase.VOTING.value else [],
            "sentence_contexts": speech_sentence_contexts(draft["speech"]) if context.phase != GamePhase.VOTING.value else [],
        }
        messages = [
            {"role": "system", "content": REVIEW_RULES},
            {"role": "user", "content": encode(review_data)},
        ]
        tools = [review_tool_spec()]
        if estimate_tokens(encode({"messages": messages, "tools": tools})) + 128 > self.config.context_token_budget:
            raise InvalidStatement("发言过长，校验请求超过上下文预算，请缩短发言")
        message = self._call_with_trace(
            messages, trace_context={**context.trace_metadata(), "stage": "validation", "attempt": attempt},
            cache_prefix=encode(fixed)[:-1],
            tools=tools, tool_choice={"type": "function", "function": {"name": "check_statement"}},
            thinking_enabled=False, temperature=0,
            model_name=self.config.review_model_name or self.config.model_name, max_tokens=4096,
        )
        calls = [tc for tc in (getattr(message, "tool_calls", None) or [])
                 if tc.function.name == "check_statement"]
        try:
            data = json.loads(calls[0].function.arguments) if len(calls) == 1 else None
        except (ValueError, TypeError):
            data = None
        if not isinstance(data, dict) or type(data.get("valid")) is not bool or not isinstance(data.get("issues"), list):
            raise InvalidStatement("一致性检查未能完成")
        if not data["valid"] or data["issues"]:
            # Feedback is quoted data, never a new game fact or system rule.
            issues = [i for i in data["issues"] if isinstance(i, str)]
            raise InvalidStatement("一致性检查：" + encode(issues)[:300])
        sources = {s.source_id: s for s in facts + reports + covers}
        segments = review_data["speech_segments"]
        segment_checks = data.get("segments")
        if not isinstance(segment_checks, list) or len(segment_checks) != len(segments):
            raise InvalidStatement("一致性检查未覆盖发言的全部分句")
        seen = set()
        verified: dict[int, StatementClaim] = {}
        for check in segment_checks:
            if not isinstance(check, dict):
                raise InvalidStatement("分句检查格式错误")
            index = check.get("segment_index")
            if type(index) is not int or not 0 <= index < len(segments) or index in seen:
                raise InvalidStatement("分句检查下标缺失或重复")
            seen.add(index)
            if check.get("supported") is not True or check.get("unsupported_details") != []:
                raise InvalidStatement(f"speech_segments[{index}] 存在无依据的细节，请删去该分句")
            if type(check.get("non_factual")) is not bool:
                raise InvalidStatement("分句检查缺少事实分类")
            segment = segments[index].rstrip("，,。！？!?；;\n")
            if re.fullmatch(r"(?:但|可|不过)?(?:我|老朽|在下)?(?:不承认行凶|不接受(?:这个|这项|你的)?指控)", segment):
                continue  # A refusal to confess is a stance, not an alibi.
            if check["non_factual"]:
                if check.get("source_id") or check.get("quote"):
                    raise InvalidStatement("非事实分句不能混入事实来源")
                continue
            source_id, quote = check.get("source_id"), check.get("quote")
            source = sources.get(source_id) if isinstance(source_id, str) else None
            covering = [c for c in draft["claims"] if segment in c["text"]]
            if (not covering or not source or not isinstance(quote, str)
                    or not quote.strip() or quote not in source.text):
                sentence = review_data["sentence_contexts"][index]
                raise InvalidStatement(
                    f"分句「{segment[:80]}」缺少对应陈述和支持整句的真实原文；"
                    f"所在完整句「{sentence[:160]}」。纯未知请独立成句用aside，个人经历请登记事实及来源。"
                )
            # The independent checker may correct a redundant/wrong citation
            # using an already visible source. Persist its actual provenance,
            # not the generator's original citation. Source classes still hold.
            compatible = [c for c in covering if (
                c["kind"] in {"reported", "inference"}
                or c["kind"] == "observed" and source.kind in {"case", "personal", "physical", "identity"}
                or c["kind"] == "cover" and source.kind == "cover")]
            if not compatible and source.kind in {"document", "testimony"} and is_record_description(segment):
                compatible = [{"kind": "reported"}]
            if not compatible:
                raise InvalidStatement(f"分句「{segment[:100]}」的类别与来源 {source_id} 不符，请纠正类别")
            verified[index] = StatementClaim(segments[index], compatible[0]["kind"], (source_id,))
        return tuple(verified[i] for i in sorted(verified))

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

    def respond_introduction(self, context: RoleContext | None = None) -> str:
        """Generate an introduction response.

        Returns:
            The introduction.
        """
        return self.respond("", GamePhase.INTRODUCTION, record_in_memory=False, context=context)

    def get_vote(
        self, known_clues: Optional[List[ClueData]] = None,
        revealed_clues: Optional[List[ClueData]] = None,
        other_chars: Optional[List[ScriptCharacter]] = None,
        discussion_history: Optional[List[str]] = None,
        context: RoleContext | None = None,
    ) -> tuple[str, str]:
        """Submit an advisory ballot using the same frozen, filtered view."""
        others = [c for c in (other_chars or []) if c.id != self.character.id]
        try:
            context = context or self._legacy_context(
                "", GamePhase.VOTING, self.case, known_clues or [],
                revealed_clues or [], others, discussion_history or [],
            )
            messages = self._build_messages("", GamePhase.VOTING, context=context)
            candidates = list(context.candidate_ids)
            if not candidates:
                return "", ""
            message = self._call_with_trace(
                messages,
                trace_context={**context.trace_metadata(), "character_name": self.name,
                               "stage": "voting", "via": "function_call"},
                cache_prefix=context.stable_prefix, tools=[vote_tool_spec()],
                tool_choice={"type": "function", "function": {"name": "submit_vote"}},
                thinking_enabled=False,
            )
        except ModelInterrupted:
            raise
        except Exception as exc:
            logger.error("[Vote Tool Error] %s: %s", self.name, exc)
            return "", ""

        target = ""
        reason = ""
        for tc in getattr(message, "tool_calls", None) or []:
            if getattr(tc, "type", "function") != "function":
                continue
            if tc.function.name != "submit_vote":
                continue
            raw_args = (tc.function.arguments or "").strip()
            args = {}
            if raw_args:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                return "", ""
            target = str(args.get("target_id") or "").strip()
            reason = str(args.get("brief_reason") or "").strip()
            break

        if not target and message.content:
            # 偶发：模型没调工具而回了纯文本 —— 走原有名字/char_X 解析兜底
            public_peers = context.payload()["characters"]
            id_match = re.search(r"char_\d+", message.content)
            target = id_match.group() if id_match else next(
                (c["id"] for c in sorted(public_peers, key=lambda c: -len(c["name"]))
                 if c["name"] and c["name"] in message.content), "",
            )
        if target not in candidates:
            return "", ""
        if reason:
            try:
                self._review_statement(encode({"speech": reason, "claims": [], "corrections": []}), context, 1)
            except ModelInterrupted:
                raise
            except Exception as exc:
                logger.warning("角色 %s 投票理由校验未通过: %s", self.name, exc)
                return "", ""
        return target, reason

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
