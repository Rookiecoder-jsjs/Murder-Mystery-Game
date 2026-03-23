# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""FastAPI main entry point for the murder mystery game - matching original API."""

import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI

from app.api.routes import router
from app.core.phases import GamePhase
from app.services.story_service import (
    StoryService,
    create_m2_client,
    ensure_stories_dir,
    save_story,
    load_story,
    list_stories,
)
from app.services.game_service import GameService


load_dotenv()


story_service = StoryService()
game_service = GameService(m2_client=create_m2_client())


# ============== Pydantic Models ==============

class CreateGameRequest(BaseModel):
    topic: str = Field(..., description="剧本主题")
    player_name: Optional[str] = Field(None, description="玩家名字")


class LoadGameRequest(BaseModel):
    story_id: str = Field(..., description="故事ID")


class AccuseRequest(BaseModel):
    character_name: str = Field(..., description="被指控的角色名字")


class SpeakRequest(BaseModel):
    message: str = Field(..., description="玩家发言内容")


class VoteRequest(BaseModel):
    character_name: str = Field(..., description="投票的角色名字")


# ============== Game Session Manager ==============

class GameSession:
    """游戏会话管理"""

    def __init__(self, archive, human_player_id: str, m2_client: OpenAI):
        from app.domain.game_manager import GameManager
        from app.agents.m2_character import M2Character

        self.archive = archive
        self.game = GameManager(archive)
        self.human_player_id = human_player_id
        self.m2_client = m2_client

        # 初始化AI角色
        self.ai_characters: Dict[str, M2Character] = {}
        for char in archive.characters:
            if char.id != human_player_id:
                self.ai_characters[char.id] = M2Character(
                    character=char,
                    client=m2_client,
                )

        # 分配初始线索
        self._distribute_initial_clues()

    def _distribute_initial_clues(self):
        """分配初始线索"""
        self.game.distribute_random_clues(self.human_player_id, 1)
        for char_id, ai in self.ai_characters.items():
            board = self.game.get_clue_board(char_id)
            if board.available:
                self.game.distribute_random_clues(char_id, 1)

    def get_player_info(self) -> Dict[str, Any]:
        char = self.game.get_character(self.human_player_id)
        return {
            "id": char.id,
            "name": char.name,
            "public_identity": char.public_identity,
            "appearance": char.appearance
        }

    def get_all_characters(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "public_identity": c.public_identity,
                "appearance": c.appearance
            }
            for c in self.archive.characters
        ]

    def get_clue_board(self) -> Dict[str, Any]:
        board = self.game.get_clue_board(self.human_player_id)

        def clue_to_info(entry):
            holder_name = "场景"
            if entry.clue.holder_id != "scene":
                holder = self.game.get_character(entry.clue.holder_id)
                if holder:
                    holder_name = holder.name
            return {
                "id": entry.clue.id,
                "content": entry.clue.content,
                "type": entry.clue.type,
                "holder_name": holder_name,
                "is_revealed": entry.status == "scene_public"
            }

        clues = [clue_to_info(e) for e in board.owned]
        scene_public = [clue_to_info(e) for e in board.scene_public]

        human_state = self.game.state.player_states[self.human_player_id]

        return {
            "clues": clues,
            "accusation_points": human_state.accusation_points,
            "scene_public_clues": scene_public
        }

    def get_game_status(self) -> Dict[str, Any]:
        actions = []
        phase = self.game.state.phase

        if phase == "introduction":
            actions = ["introduce"]
        elif phase == "investigation":
            actions = ["view_clues", "discuss", "accuse"]
        elif phase == "discussion":
            actions = ["speak", "view_clues", "accuse", "vote", "return_investigation"]
        elif phase == "voting":
            actions = ["vote"]
        elif phase == "reveal":
            actions = []

        return {
            "game_id": self.archive.id,
            "phase": phase,
            "round": self.game.state.round,
            "max_rounds": self.game.state.max_rounds,
            "player": self.get_player_info(),
            "characters": self.get_all_characters(),
            "available_actions": actions
        }

    def next_phase(self):
        self.game.next_phase()

    def player_introduce(self, message: str = "") -> Dict[str, Any]:
        human_char = self.game.get_character(self.human_player_id)

        ai_introductions = []
        for char_id, ai in self.ai_characters.items():
            response = ai.respond_introduction()
            ai_introductions.append({
                "speaker": ai.name,
                "message": response
            })

        self.next_phase()

        return {
            "player_introduction": message or f"大家好，我是{human_char.name}，{human_char.public_identity}。",
            "ai_introductions": ai_introductions,
            "new_phase": self.game.state.phase
        }

    def accuse(self, character_name: str) -> Dict[str, Any]:
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")

        if not self.game.can_accuse(self.human_player_id):
            raise HTTPException(status_code=400, detail="已经没有指认次数了")

        correct, message = self.game.accuse(self.human_player_id, target_id)

        return {
            "correct": correct,
            "message": message,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner
        }

    def player_speak(self, message: str) -> list[Dict[str, Any]]:
        human_char = self.game.get_character(self.human_player_id)
        self.game.add_discussion(self.human_player_id, message)

        messages = [{"speaker": human_char.name, "message": message}]

        for char_id, ai in self.ai_characters.items():
            ai_state = self.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                continue

            known = self.game.get_player_clues(char_id)
            response = ai.respond(
                user_input=message,
                phase=GamePhase.DISCUSSION,
                known_clues=known,
                revealed_clues=self.game.get_revealed_clues(),
                other_chars=[
                    c for c in self.archive.characters if c.id != char_id
                ],
                discussion_history=self.game.state.discussion_history,
            )

            messages.append({
                "speaker": ai.name,
                "message": response
            })

            self.game.add_discussion(char_id, response)

        return messages

    def vote(self, character_name: str) -> Dict[str, Any]:
        target_id = self.game.get_character_id_by_name(character_name)
        if not target_id:
            raise HTTPException(status_code=400, detail=f"找不到角色: {character_name}")

        self.game.submit_vote(self.human_player_id, target_id)

        for char_id, ai in self.ai_characters.items():
            ai_state = self.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                continue

            ai_vote = ai.get_vote()
            if ai_vote in self.game.alive_players:
                self.game.submit_vote(char_id, ai_vote)

        winner, conditions, is_tied = self.game.tally_votes()
        ended, result = self.game.check_voting_result()

        return {
            "votes": {},
            "result": result,
            "game_ended": self.game.state.game_ended,
            "winner": self.game.state.winner
        }

    def get_reveal_info(self) -> Dict[str, Any]:
        return {
            "story_content": self.archive.story_content,
            "winner": self.game.state.winner or "unknown",
            "case_info": {
                "title": self.archive.case.title,
                "background": self.archive.case.background,
                "victim": self.archive.case.victim,
                "crime": self.archive.case.crime,
                "motive": self.archive.case.motive,
                "true_killer": self.game.killer_id
            }
        }


# ============== Session Manager ==============

sessions: Dict[str, GameSession] = {}


def get_session(game_id: str) -> GameSession:
    if game_id not in sessions:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return sessions[game_id]


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_stories_dir()
    yield


app = FastAPI(
    title="剧本杀 API",
    description="剧本杀游戏后端服务 - CAMEL框架版",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ============== API Endpoints ==============

@app.get("/")
async def root():
    return {"message": "剧本杀 API", "version": "1.0.0"}


@app.get("/stories")
async def list_available_stories():
    """列出所有可用故事"""
    stories = list_stories()
    return {"stories": stories}


@app.post("/games")
async def create_game(request: CreateGameRequest):
    """创建新游戏"""
    try:
        archive = story_service.create_story(request.topic, show_reasoning=True)
        if not archive:
            raise HTTPException(status_code=500, detail="生成案件失败")

        import random
        char_ids = [c.id for c in archive.characters]
        human_id = random.choice(char_ids)

        session = GameSession(archive, human_id, create_m2_client())
        game_id = str(uuid.uuid4())
        sessions[game_id] = session

        return {
            "game_id": game_id,
            "story_id": archive.id,
            "topic": request.topic,
            "phase": session.game.state.phase,
            "player": session.get_player_info(),
            "characters": session.get_all_characters()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/games/load")
async def load_game(request: LoadGameRequest):
    """加载已有游戏"""
    try:
        archive = story_service.get_story(request.story_id)
        if not archive:
            raise HTTPException(status_code=404, detail="故事不存在")

        import random
        char_ids = [c.id for c in archive.characters]
        human_id = random.choice(char_ids)

        session = GameSession(archive, human_id, create_m2_client())
        game_id = str(uuid.uuid4())
        sessions[game_id] = session

        return {
            "game_id": game_id,
            "story_id": archive.id,
            "phase": session.game.state.phase,
            "player": session.get_player_info(),
            "characters": session.get_all_characters()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/games/{game_id}")
async def get_game_status(game_id: str):
    session = get_session(game_id)
    return session.get_game_status()


@app.get("/games/{game_id}/clues")
async def get_clues(game_id: str):
    session = get_session(game_id)
    return session.get_clue_board()


@app.post("/games/{game_id}/introduce")
async def player_introduce(game_id: str, message: str = ""):
    session = get_session(game_id)

    if session.game.state.phase != "introduction":
        raise HTTPException(status_code=400, detail="当前不是自我介绍阶段")

    return session.player_introduce(message)


@app.post("/games/{game_id}/next-phase")
async def advance_phase(game_id: str):
    session = get_session(game_id)

    # 如果是讨论阶段，需要检查回合数
    if session.game.state.phase == "discussion":
        if session.game.state.round >= session.game.state.max_rounds:
            # 回合结束，切换到投票阶段
            session.game.next_phase()
        else:
            # 增加回合数
            session.game.state.round += 1
    else:
        session.game.next_phase()

    return {"phase": session.game.state.phase, "round": session.game.state.round}


@app.post("/games/{game_id}/return-to-investigation")
async def return_to_investigation(game_id: str):
    """返回搜证阶段"""
    session = get_session(game_id)

    if session.game.state.phase not in ["discussion", "voting"]:
        raise HTTPException(status_code=400, detail="只能在讨论或投票阶段返回搜证")

    from app.core.phases import GamePhase
    session.game.set_phase(GamePhase.INVESTIGATION)
    session.game.state.discussion_history = []  # 清空讨论历史

    # 返回搜证阶段时，分配新线索给玩家
    session.game.distribute_random_clues(session.human_player_id, 1)

    # 同时也给AI角色分配线索
    for char_id, ai in session.ai_characters.items():
        session.game.distribute_random_clues(char_id, 1)

    return {"phase": session.game.state.phase, "round": session.game.state.round}


@app.post("/games/{game_id}/start-voting")
async def start_voting(game_id: str):
    """直接从讨论阶段进入投票阶段"""
    session = get_session(game_id)

    if session.game.state.phase != "discussion":
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")

    from app.core.phases import GamePhase
    session.game.set_phase(GamePhase.VOTING)
    session.game.state.turn = 0

    return {"phase": session.game.state.phase, "round": session.game.state.round}


@app.post("/games/{game_id}/accuse")
async def accuse(game_id: str, request: AccuseRequest):
    session = get_session(game_id)
    result = session.accuse(request.character_name)

    if result["game_ended"]:
        reveal_info = session.get_reveal_info()
        return {**result, "reveal": reveal_info}

    return result


@app.post("/games/{game_id}/speak")
async def speak(game_id: str, request: SpeakRequest):
    session = get_session(game_id)

    if session.game.state.phase != "discussion":
        raise HTTPException(status_code=400, detail="当前不是讨论阶段")

    messages = session.player_speak(request.message)

    return {
        "messages": messages,
        "phase": session.game.state.phase
    }


@app.post("/games/{game_id}/vote")
async def vote(game_id: str, request: VoteRequest):
    session = get_session(game_id)

    if session.game.state.phase != "voting":
        raise HTTPException(status_code=400, detail="当前不是投票阶段")

    result = session.vote(request.character_name)

    if result["game_ended"]:
        reveal_info = session.get_reveal_info()
        return {**result, "reveal": reveal_info}

    # 投票完成但游戏未结束（平票），返回讨论阶段
    return {
        "votes": result.get("votes", {}),
        "result": result.get("result", ""),
        "game_ended": False,
        "winner": None,
        "phase": session.game.state.phase  # 当前还是voting，但前端需要知道是平票
    }


@app.get("/games/{game_id}/reveal")
async def reveal(game_id: str):
    session = get_session(game_id)
    return session.get_reveal_info()


@app.get("/games/{game_id}/discussion-history")
async def get_discussion_history(game_id: str):
    session = get_session(game_id)
    return {"history": session.game.state.discussion_history}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
