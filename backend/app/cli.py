# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""CLI entry point for the murder mystery game."""

import asyncio
import os
import sys
import random
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from colorama import Fore, init

from app.core.phases import GamePhase
from app.services.story_service import (
    StoryService,
    create_deepseek_client,
    create_roleplay_client,
    save_story,
    list_stories,
    ensure_stories_dir,
)
from app.domain.game_manager import GameManager
from app.agents.roleplay_character import RoleplayCharacter

load_dotenv()
init(autoreset=True)


class MurderMysteryCLI:
    """CLI interface for the murder mystery game."""

    def __init__(self):
        self.story_service = StoryService()
        self.archive = None
        self.session = None
        self.roleplay_client = None

    def _setup_clients(self):
        self.roleplay_client = create_roleplay_client()

    def _print_header(self):
        print(Fore.CYAN + "=" * 50)
        print(Fore.CYAN + "  剧本杀 - CAMEL 框架版")
        print(Fore.CYAN + "=" * 50)

    def _show_stories(self):
        stories = list_stories()
        if not stories:
            print(Fore.YELLOW + "\n暂无保存的故事")
            return None

        print(Fore.YELLOW + "\n【已保存的故事】")
        for i, s in enumerate(stories, 1):
            print(Fore.GREEN + f"  {i}. {s['title']} ({s['topic']}) - {s['num_characters']}个角色")
        return stories

    def _show_characters(self):
        if not self.session:
            return

        print(Fore.YELLOW + "\n【角色列表】")
        for char in self.archive.characters:
            marker = " [你]" if char.id == self.session.human_player_id else ""
            killer_mark = " [凶手]" if char.is_killer else ""
            print(
                Fore.GREEN
                + f"  {char.id}. {char.name}（{char.public_identity}）{marker}{killer_mark}"
            )

    def _show_clue_board(self):
        if not self.session:
            return

        clue_board = self.session.game.get_clue_board(self.session.human_player_id)

        print(Fore.YELLOW + "\n【线索看板】")

        if clue_board.owned:
            print(Fore.GREEN + "  已获得线索:")
            for entry in clue_board.owned:
                print(f"    - {entry.clue.content}")
        else:
            print(Fore.WHITE + "  已获得线索: 无")

        if clue_board.scene_public:
            print(Fore.CYAN + "  场景公开线索:")
            for entry in clue_board.scene_public:
                print(f"    - {entry.clue.content}")

    async def run(self):
        self._setup_clients()
        self._print_header()

        print(Fore.YELLOW + "\n请选择:")
        print(Fore.YELLOW + "  1. 生成新剧本")
        print(Fore.YELLOW + "  2. 加载已有故事")
        print(Fore.YELLOW + "  3. 从文件导入故事")

        choice = input(Fore.YELLOW + "\n请选择: ").strip()

        if choice == "1":
            topic = input(Fore.YELLOW + "\n请输入剧本主题: ").strip()
            if not topic:
                print(Fore.RED + "主题不能为空！")
                return

            print(Fore.CYAN + "\n正在生成剧本...")
            self.archive = self.story_service.create_story(topic, show_reasoning=True)
            if not self.archive:
                print(Fore.RED + "生成失败！")
                return

        elif choice == "2":
            stories = self._show_stories()
            if not stories:
                return

            idx = input(Fore.YELLOW + "\n请选择编号: ").strip()
            try:
                idx = int(idx) - 1
                if 0 <= idx < len(stories):
                    story_id = stories[idx]["id"]
                    self.archive = self.story_service.get_story(story_id)
                    if not self.archive:
                        print(Fore.RED + "加载失败!")
                        return
                else:
                    print(Fore.RED + "无效选择!")
                    return
            except ValueError:
                print(Fore.RED + "无效选择!")
                return

        elif choice == "3":
            json_path = input(Fore.YELLOW + "\n请输入故事JSON文件路径: ").strip()
            if not os.path.exists(json_path):
                print(Fore.RED + "文件不存在!")
                return

            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            from app.domain.models import StoryArchive
            self.archive = StoryArchive.from_dict(data)

        else:
            print(Fore.RED + "无效选择!")
            return

        print(Fore.GREEN + f"\n剧本加载成功！")
        print(Fore.CYAN + f"【{self.archive.title}】")
        print(Fore.YELLOW + f"\n案件概要:")
        print(Fore.WHITE + f"  时间: {self.archive.case.time}")
        print(Fore.WHITE + f"  地点: {self.archive.case.location}")
        print(Fore.WHITE + f"  受害者: {self.archive.case.victim}")
        print(Fore.WHITE + f"  {self.archive.case.background[:200]}...")

        # 随机分配角色给玩家
        char_id = random.choice([c.id for c in self.archive.characters])
        player_char = None
        for c in self.archive.characters:
            if c.id == char_id:
                player_char = c
                break

        print(Fore.YELLOW + f"\n你被分配扮演: {player_char.name}（{player_char.public_identity}）")

        # 初始化游戏会话
        self.session = type('Session', (), {})()
        self.session.archive = self.archive
        self.session.human_player_id = char_id
        self.session.game = GameManager(self.archive)

        # 初始化AI角色
        self.session.ai_characters = {}
        for char in self.archive.characters:
            if char.id != char_id:
                self.session.ai_characters[char.id] = RoleplayCharacter(
                    character=char,
                    client=self.roleplay_client,
                )

        # 分配初始线索
        self.session.game.distribute_random_clues(char_id, 1)
        for cid, ai in self.session.ai_characters.items():
            board = self.session.game.get_clue_board(cid)
            if board.available:
                self.session.game.distribute_random_clues(cid, 1)

        self._show_characters()
        await self._game_loop()

    async def _game_loop(self):
        while not self.session.game.state.game_ended:
            phase = self.session.game.state.phase

            if phase == "introduction":
                await self._phase_introduction()
            elif phase == "investigation":
                await self._phase_investigation()
            elif phase == "discussion":
                await self._phase_discussion()
            elif phase == "voting":
                await self._phase_voting()
            elif phase == "reveal":
                await self._phase_reveal()
                break

    async def _phase_introduction(self):
        print(Fore.CYAN + "\n" + "=" * 50)
        print(Fore.CYAN + "  自我介绍阶段")
        print(Fore.CYAN + "=" * 50)

        # 显示案件背景
        print(Fore.YELLOW + "\n【案件背景】")
        print(Fore.WHITE + f"{self.archive.case.background}")

        # 显示案件信息
        print(Fore.YELLOW + "\n【案件信息】")
        print(Fore.WHITE + f"  案发时间: {self.archive.case.time}")
        print(Fore.WHITE + f"  案发地点: {self.archive.case.location}")
        print(Fore.WHITE + f"  受害者: {self.archive.case.victim}")
        print(Fore.WHITE + f"  案件类型: {self.archive.case.crime}")

        # 显示玩家扮演的角色详细信息
        human_char = self.session.game.get_character(self.session.human_player_id)
        if human_char:
            print(Fore.YELLOW + "\n【你扮演的角色】")
            print(Fore.GREEN + f"  姓名: {human_char.name}")
            print(Fore.WHITE + f"  身份: {human_char.public_identity}")
            if human_char.appearance:
                print(Fore.WHITE + f"  外貌: {human_char.appearance}")
            if human_char.backstory:
                print(Fore.WHITE + f"  背景: {human_char.backstory}")
            if human_char.relationship_with_victim:
                print(Fore.WHITE + f"  与受害者关系: {human_char.relationship_with_victim}")
            if human_char.alibi:
                print(Fore.WHITE + f"  不在场证明: {human_char.alibi}")

        # 显示所有角色列表（不显示秘密）
        print(Fore.YELLOW + "\n【嫌疑人名单】")
        for char in self.archive.characters:
            if char.id == self.session.human_player_id:
                continue  # 不显示玩家自己的信息
            marker = " [凶手]" if char.is_killer else ""
            print(Fore.GREEN + f"  {char.name}（{char.public_identity}）{marker}")

        # 让AI角色进行自我介绍
        print(Fore.YELLOW + "\n" + "-" * 40)
        print(Fore.YELLOW + "【自我介绍】")
        print(Fore.YELLOW + "-" * 40)

        for char_id, ai in self.session.ai_characters.items():
            response = ai.respond_introduction()
            char = self.session.game.get_character(char_id)
            if char:
                print(Fore.GREEN + f"\n【{char.name}】: {response}")

        self.session.game.next_phase()
        print(Fore.YELLOW + "\n按回车键进入搜证阶段...")
        input()

    async def _phase_investigation(self):
        print(Fore.CYAN + "\n" + "=" * 40)
        print(Fore.CYAN + f"  搜证阶段 - 第{self.session.game.state.investigation_count}次")
        print(Fore.CYAN + "=" * 40)

        self._show_clue_board()

        print(Fore.YELLOW + "\n操作:")
        print(Fore.YELLOW + "  1. 搜证（随机获得线索）")
        print(Fore.YELLOW + "  2. 查看线索")
        print(Fore.YELLOW + "  3. 进入讨论")
        print(Fore.YELLOW + "  q. 退出")

        choice = input(Fore.YELLOW + "\n请选择: ").strip()

        if choice == "1":
            clues = self.session.game.distribute_random_clues(self.session.human_player_id, 1)
            if clues:
                print(Fore.GREEN + "\n获得线索:")
                for c in clues:
                    print(Fore.GREEN + f"  - {c.content}")
            else:
                print(Fore.YELLOW + "没有可获得的线索了。")
            # 搜证完成后自动进入讨论阶段
            self.session.game.next_phase()
            return
        elif choice == "2":
            self._show_clue_board()
        elif choice == "3":
            self.session.game.next_phase()
            return
        elif choice.lower() == "q":
            exit(0)

    async def _phase_discussion(self):
        print(Fore.CYAN + "\n" + "=" * 40)
        print(Fore.CYAN + f"  讨论阶段 - 回合 {self.session.game.state.round}/{self.session.game.state.max_rounds}")
        print(Fore.CYAN + "=" * 40)

        print(Fore.YELLOW + "\n讨论历史:")
        for line in self.session.game.state.discussion_history[-10:]:
            print(Fore.WHITE + f"  {line}")

        # 检查玩家是否还能指认
        can_accuse = self.session.game.can_accuse(self.session.human_player_id)

        print(Fore.YELLOW + "\n操作:")
        print(Fore.YELLOW + "  1. 发言")
        print(Fore.YELLOW + "  2. 搜证")
        print(Fore.YELLOW + "  3. 查看线索")
        print(Fore.YELLOW + "  4. 指认凶手")
        print(Fore.YELLOW + "  next. 进入投票")
        print(Fore.YELLOW + "  q. 退出")

        choice = input(Fore.YELLOW + "\n请选择: ").strip()

        if choice == "1":
            user_input = input(Fore.YELLOW + "你的发言: ").strip()
            if user_input:
                human_char = self.session.game.get_character(self.session.human_player_id)
                self.session.game.add_discussion(self.session.human_player_id, user_input)

                print(Fore.YELLOW + "\n等待AI角色回应...")

                for char_id, ai in self.session.ai_characters.items():
                    ai_state = self.session.game.state.player_states.get(char_id)
                    if not ai_state or not ai_state.is_alive:
                        continue

                    known = self.session.game.get_player_clues(char_id)
                    response = ai.respond(
                        user_input=user_input,
                        phase=GamePhase.DISCUSSION,
                        known_clues=known,
                        revealed_clues=self.session.game.get_revealed_clues(),
                        other_chars=[
                            c for c in self.archive.characters if c.id != char_id
                        ],
                        discussion_history=self.session.game.state.discussion_history,
                    )

                    char = self.session.game.get_character(char_id)
                    if char:
                        print(Fore.GREEN + f"\n【{char.name}】: {response}")

                    self.session.game.add_discussion(char_id, response)

        elif choice == "2":
            clues = self.session.game.distribute_random_clues(self.session.human_player_id, 1)
            if clues:
                print(Fore.GREEN + "\n获得线索:")
                for c in clues:
                    print(Fore.GREEN + f"  - {c.content}")
            else:
                print(Fore.YELLOW + "没有可获得的线索了。")

        elif choice == "3":
            self._show_clue_board()

        elif choice == "4":
            if not can_accuse:
                print(Fore.RED + "你已经使用过指认功能！")
            else:
                await self._do_accuse()

        elif choice.lower() == "next":
            if self.session.game.state.round >= self.session.game.state.max_rounds:
                self.session.game.next_phase()
            else:
                self.session.game.state.round += 1
                print(Fore.YELLOW + f"\n进入第 {self.session.game.state.round} 回合")

    async def _do_accuse(self):
        """执行指认"""
        print(Fore.CYAN + "\n" + "=" * 40)
        print(Fore.CYAN + "  指认凶手")
        print(Fore.CYAN + "=" * 40)

        print(Fore.YELLOW + "\n请选择你要指认的嫌疑人:")

        chars = [
            c for c in self.session.archive.characters
            if c.id != self.session.human_player_id
        ]
        for i, char in enumerate(chars, 1):
            print(Fore.YELLOW + f"  {i}. {char.name}（{char.public_identity}）")

        # 循环直到输入有效
        target_id = None
        while True:
            target_input = input(Fore.YELLOW + "\n请选择编号: ").strip()
            try:
                idx = int(target_input) - 1
                if 0 <= idx < len(chars):
                    target_id = chars[idx].id
                    print(Fore.YELLOW + f"\n你指认了: {chars[idx].name}")
                    break
                else:
                    print(Fore.RED + f"请输入1-{len(chars)}之间的数字")
            except ValueError:
                if target_input in [c.id for c in chars]:
                    target_id = target_input
                    char = self.session.game.get_character(target_id)
                    print(Fore.YELLOW + f"\n你指认了: {char.name if char else target_id}")
                    break
                print(Fore.RED + "请输入有效的编号或角色ID")

        # 执行指认
        is_correct, result = self.session.game.accuse(
            self.session.human_player_id,
            target_id
        )

        print(Fore.CYAN + f"\n{result}")

        # 指认后直接进入真相揭晓
        self.session.game.next_phase()

    async def _phase_voting(self):
        print(Fore.CYAN + "\n" + "=" * 40)
        print(Fore.CYAN + "  投票阶段")
        print(Fore.CYAN + "=" * 40)

        print(Fore.YELLOW + "\n请投票选择凶手:")

        chars = [
            c for c in self.session.archive.characters
            if c.id != self.session.human_player_id
        ]
        for i, char in enumerate(chars, 1):
            print(Fore.YELLOW + f"  {i}. {char.name}（{char.public_identity}）")

        # 循环直到输入有效
        target_id = None
        while True:
            target_input = input(Fore.YELLOW + "\n请选择编号: ").strip()
            try:
                idx = int(target_input) - 1
                if 0 <= idx < len(chars):
                    target_id = chars[idx].id
                    print(Fore.YELLOW + f"\n你投票给: {chars[idx].name}")
                    break
                else:
                    print(Fore.RED + f"请输入1-{len(chars)}之间的数字")
            except ValueError:
                # 尝试直接匹配ID
                if target_input in [c.id for c in chars]:
                    target_id = target_input
                    char = self.session.game.get_character(target_id)
                    print(Fore.YELLOW + f"\n你投票给: {char.name if char else target_id}")
                    break
                print(Fore.RED + "请输入有效的编号或角色ID")

        self.session.game.submit_vote(self.session.human_player_id, target_id)

        print(Fore.YELLOW + "\n等待AI角色投票...")

        for char_id, ai in self.session.ai_characters.items():
            ai_state = self.session.game.state.player_states.get(char_id)
            if not ai_state or not ai_state.is_alive:
                continue

            ai_vote = ai.get_vote()
            if ai_vote in self.session.game.alive_players:
                self.session.game.submit_vote(char_id, ai_vote)
                vote_char = self.session.game.get_character(ai_vote)
                char = self.session.game.get_character(char_id)
                if vote_char and char:
                    print(Fore.GREEN + f"【{char.name}】投票给: {vote_char.name}")

        winner, conditions, is_tied = self.session.game.tally_votes()
        ended, result = self.session.game.check_voting_result()

        if ended:
            print(Fore.CYAN + f"\n{result}")
            self.session.game.next_phase()
        else:
            print(Fore.YELLOW + f"\n{result}")

    async def _phase_reveal(self):
        print(Fore.CYAN + "\n" + "=" * 40)
        print(Fore.CYAN + "  真相揭晓")
        print(Fore.CYAN + "=" * 40)

        summary = self.session.game.get_game_summary()
        print(Fore.WHITE + f"\n{summary}")

    def run_sync(self):
        ensure_stories_dir()
        asyncio.run(self.run())


def main():
    cli = MurderMysteryCLI()
    try:
        cli.run_sync()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n游戏结束。再见！")


if __name__ == "__main__":
    main()
