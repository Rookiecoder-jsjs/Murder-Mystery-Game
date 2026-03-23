# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Story generator agent using DeepSeek Reasoner."""

import json
import re
from typing import Any, Optional

from camel.agents import ChatAgent
from camel.messages import BaseMessage

from app.domain.models import (
    StoryArchive,
    CaseData,
    ScriptCharacter,
    ClueData,
)


class StoryGeneratorAgent:
    """Agent for generating murder mystery stories using DeepSeek Reasoner.

    This agent uses the DeepSeek Reasoner model to generate comprehensive
    murder mystery stories including characters, clues, and the truth.
    """

    def __init__(self, model: Any):
        """Initialize the story generator agent.

        Args:
            model: The model backend to use (DeepSeek).
        """
        self._model = model

        system_msg = BaseMessage.make_assistant_message(
            role_name="StoryGenerator",
            content=(
                "你是一个专业的剧本杀故事生成专家。你能够根据用户给定的主题，"
                "生成完整的谋杀案剧本，包括背景故事、角色设定、线索设计和真相揭示。"
            ),
        )

        self._agent = ChatAgent(system_message=system_msg, model=model)

    def generate_story(self, topic: str, show_reasoning: bool = False) -> StoryArchive:
        """Generate a murder mystery story based on the topic.

        Args:
            topic: The story topic/theme.
            show_reasoning: Whether to show the model's reasoning process.

        Returns:
            A StoryArchive containing the complete story.
        """
        prompt = self._build_generation_prompt(topic)

        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=prompt,
        )

        try:
            response = self._agent.step(user_msg)

            if hasattr(response, 'msg') and response.msg:
                content = response.msg.content
            elif hasattr(response, 'msgs') and response.msgs:
                content = response.msgs[0].content if response.msgs else ""
            else:
                content = str(response)

            if show_reasoning:
                reasoning = getattr(response, 'reasoning_content', '')
                if reasoning:
                    print(f"\n[思考过程]\n{reasoning[:500]}...")

            return self._parse_story(content, topic)

        except Exception as e:
            raise RuntimeError(f"Failed to generate story: {e}")

    def _build_generation_prompt(self, topic: str) -> str:
        """Build the story generation prompt.

        Args:
            topic: The story topic.

        Returns:
            The formatted prompt.
        """
        return f"""请为「{topic}」这个主题创作一个剧本杀故事。

请生成一个完整的谋杀案剧本，包括：

1. **案件背景**：故事发生的场景、时间、地点、氛围
2. **受害者信息**：受害者姓名、背景
3. **犯罪描述**：犯罪经过
4. **真凶设定**：凶手是谁、动机、手法
5. **角色列表**（4-6个角色）：
   - 每个角色的：ID、名字、公开身份、隐藏秘密、性格特点、说话风格
   - 与受害者的关系
   - 持有线索
   - 作案动机（凶手角色）
6. **线索列表**（6-10条线索）：
   - 每条线索的：ID、内容、类型（物证/证言/文书）
   - 线索指向
7. **完整真相**：案件的全部真相和推理过程

请以JSON格式输出，格式如下：
{{
    "title": "故事标题",
    "case": {{
        "title": "案件名称",
        "background": "故事背景",
        "victim": "受害者姓名",
        "crime": "犯罪描述",
        "true_killer": "凶手ID",
        "motive": "作案动机",
        "location": "地点",
        "time": "时间"
    }},
    "characters": [
        {{
            "id": "char_1",
            "name": "角色名",
            "public_identity": "公开身份",
            "secret": "隐藏秘密",
            "is_killer": false,
            "clues": ["clue_1"],
            "alibi": "不在场证明",
            "dialogue_style": "说话风格",
            "backstory": "背景故事",
            "relationship_with_victim": "与受害者关系",
            "appearance": "外貌特征"
        }}
    ],
    "clues": [
        {{
            "id": "clue_1",
            "content": "线索内容",
            "type": "physical",
            "holder_id": "char_1",
            "reveal_to_all": false
        }}
    ],
    "story_content": "完整真相揭示"
}}

只输出JSON，不要其他内容。用中文回复。"""

    def _parse_story(self, content: str, topic: str) -> StoryArchive:
        """Parse the generated content into a StoryArchive.

        Args:
            content: The generated JSON content.
            topic: The original topic.

        Returns:
            A StoryArchive instance.
        """
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            raise ValueError("Failed to parse story JSON from response")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON: {e}")

        characters = []
        for char_data in data.get("characters", []):
            characters.append(ScriptCharacter(**char_data))

        clues = []
        for clue_data in data.get("clues", []):
            clues.append(ClueData(**clue_data))

        case = CaseData(
            title=data["case"]["title"],
            background=data["case"]["background"],
            victim=data["case"]["victim"],
            crime=data["case"]["crime"],
            true_killer=data["case"]["true_killer"],
            motive=data["case"]["motive"],
            location=data["case"].get("location", ""),
            time=data["case"].get("time", ""),
        )

        return StoryArchive(
            id=StoryArchive.generate_id(),
            created_at=StoryArchive.generate_timestamp(),
            topic=topic,
            title=data.get("title", f"{topic}谋杀案"),
            case=case,
            characters=characters,
            clues=clues,
            story_content=data.get("story_content", ""),
        )
