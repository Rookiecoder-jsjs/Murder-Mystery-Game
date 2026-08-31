# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Story generation and storage service - matching original Script_kill project."""

import os
import json
import re
import time
from typing import Optional, List, Dict, Any

from openai import OpenAI

from app.core.config import get_config
from app.core.llm_trace import trace_llm_chat
from app.core.logging import get_logger
from app.domain.models import StoryArchive, CaseData, ClueData, ScriptCharacter
from app.services.image_service import PortraitService, delete_story_portraits


logger = get_logger(__name__)


# ============ Prompt Template (from original project) ============

CASE_PROMPT_TEMPLATE = """创建一个复杂的剧本杀案件，满足以下要求：

## 1. 案件背景（沉浸式设定）
- 时间地点：具体且有画面感
- 社会环境：涉及至少2个社会阶层或利益集团的冲突
- 历史背景：与时代背景紧密关联，有时代特色
- 营造强烈的氛围感和沉浸感

## 2. 受害者设定（立体鲜活的角色）
- 姓名、身份、社会地位、外貌特征
- 与每个嫌疑人的具体关系（不能用"与嫌疑人有矛盾"这种模糊描述）
- 死亡方式和时间（含具体细节）
- 一个隐藏的秘密（死后才被发现）

## 3. 嫌疑人设定（每个角色都是主角）
每个嫌疑人需要包含：
- 姓名、身份、年龄、外貌特征
- 与受害者的具体关系（亲情/爱情/友情/利益）
- 作案动机（深层心理动机，不只是表面理由）
- 隐藏的秘密（与案件相关但玩家不知道）
- 不在场证明（含真假两条，需要推理）
- 人物背景故事（至少3句话的家庭/成长经历）
- 说话风格和性格特点
- 持有或知道的线索
- 所有角色都要有完整的设定，即使不是凶手也要有丰富的故事

## 4. 角色关系网络
- 构建复杂的人物关系图
- 至少3条独立但交叉的故事线
- 角色之间的秘密互相交织
- 表面关系 vs 真实关系的对比
- 包含至少一个双重身份或隐藏身份

## 5. 线索设计（10-15条）
物证类：直接指向凶手但可被栽赃
人证类：证人可能有偏见、说谎或记忆错误
旁证类：需要逻辑推理串联
每条线索都要有完整的故事背景和时间线


## 6. 结局设计
- 凶手必须能够被推理出（非随机）
- 所有线索在游戏结束时都能串联
- 提供完整的真相叙述（时间线、动机、手法）
- 真相要令人信服，有多重反转

## 7. 核心诡计与推理闭环
- 案件必须包含至少一个本格推理的核心诡计（密室/时间差/身份替换/毒药延时/误导性现场等）
- 诡计需有完整的物理或心理逻辑支撑，且能被证据链证实
- 真凶的作案过程必须与所有证据完美吻合，而其他嫌疑人只能解释部分证据
- 真相部分需逐一说明每条关键线索如何指向真凶，并解释其他嫌疑人为何不成立

## 8. 时代特色植入
- 案件的核心元素（手法、工具、动机、关键地点）必须与设定年代（1930年代）紧密绑定
- 例如：使用当时特有的物品（煤气灯、留声机、老式电话）、社会制度（租界管辖权、帮派势力）、文化习俗等
- 禁止出现任何明显超越时代的技术或物品

## 9. 输出格式
请以JSON格式输出，包含以下结构：
{{
    "title": "案件名称",
    "background": "详细的故事背景（200字以上）",
    "location": "具体地点",
    "time": "具体时间",
    "victim": {{
        "name": "受害者姓名",
        "identity": "受害者身份",
        "appearance": "外貌特征",
        "relationship_with_suspects": "与每个嫌疑人的关系描述"
    }},
    "true_killer_id": "凶手ID",
    "characters": [
        {{
            "id": "char_1",
            "name": "角色姓名",
            "public_identity": "公开身份",
            "age": "年龄",
            "appearance": "外貌特征",
            "secret": "隐藏秘密（玩家不知道）",
            "backstory": "背景故事（至少3句话）",
            "relationship_with_victim": "与受害者关系",
            "motive": "作案动机（仅凶手有）",
            "alibi": "不在场证明（包含真假两条）",
            "dialogue_style": "说话风格",
            "clue_ids": ["拥有的线索ID"],
            "is_killer": false
        }}
    ],
    "clues": [
        {{
            "id": "clue_1",
            "content": "线索内容",
            "type": "physical/testimony/document",
            "holder_id": "持有者ID（角色或scene）",
            "reveal_to_all": false,
            "required_clue_id": null
        }}
    ],
    "truth": "完整的真相叙述，包括时间线、动机、手法（300字以上）"
}}

请生成JSON格式，只输出JSON，不要其他内容。用中文回复。"""


# 故事生成的 system 人设 —— 让模型以本格推理作家的身份落笔，
# 比单纯在 user 消息里塞约束更能稳定产出结构完整的案卷。
STORY_SYSTEM_PROMPT = (
    "你是一位深耕1930年代题材的本格推理剧本杀作家。"
    "你擅长设计时代贴合的核心诡计与多线交叉的人物关系，"
    "并且能写出经得起证据链推敲的真相。"
    "无论用户要求什么主题，你都严格按规定的JSON结构输出完整案件设定："
    "必须是合法JSON，不要使用Markdown代码块，不要输出JSON以外的任何文字。"
)

# 生成 token 上限：模板实际需要 ~4-9k tokens，24k 留足余量防截断。
STORY_MAX_TOKENS = 24 * 1024


# ============ Model Factory Functions ============

def create_deepseek_client() -> OpenAI:
    """Create DeepSeek client for story generation (v4-pro, thinking off)."""
    config = get_config().deepseek
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def create_roleplay_client() -> OpenAI:
    """Create client for AI character roleplay (v4-flash by default)."""
    config = get_config().roleplay
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


# ============ Story Generation ============

def generate_story_text(
    prompt: str,
    client: OpenAI,
    show_reasoning: bool = False
) -> str:
    """Generate content with the story-generation model.

    Thinking mode is disabled: the task is essentially "fill in a template
    JSON". Measured on deepseek-v4-pro, keeping thinking enabled burns
    3x the time (~305s vs ~99s) by producing 12k+ chars of reasoning the
    JSON never uses. ``max_tokens`` stays well above the ~4-9k tokens the
    template actually needs, so output is never truncated.

    Args:
        prompt: The prompt text.
        client: DeepSeek client.
        show_reasoning: Whether to log the reasoning process.

    Returns:
        The generated content.
    """
    from openai import APIError

    config = get_config().deepseek
    messages = [
        {"role": "system", "content": STORY_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=config.model_name,
            messages=messages,
            max_tokens=STORY_MAX_TOKENS,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except APIError as e:
        trace_llm_chat(
            model=config.model_name,
            kind="story_generation",
            messages=messages,
            error=str(e),
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        raise RuntimeError(f"Story generation failed ({config.model_name}): {e}") from e

    reasoning = getattr(response.choices[0].message, "reasoning_content", None) or ""
    content = response.choices[0].message.content or ""
    trace_llm_chat(
        model=config.model_name,
        kind="story_generation",
        messages=messages,
        response=content,
        reasoning=reasoning,
        usage=getattr(response, "usage", None),
        duration_ms=int((time.monotonic() - start) * 1000),
    )

    if show_reasoning and reasoning:
        logger.info("[思考过程] %s...", reasoning[:800])

    return content


# ============ Story Generation ============

def extract_story_json(content: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object robustly from a model's free-form reply.

    Strips a wrapping Markdown code fence first, then takes the whole
    span between the first '{' and the last '}' and json.loads it — more
    tolerant than a blind ``re.search(r'\\{.*\\}')`` of text the model
    decorated with prose around the JSON.

    Returns:
        Parsed dict, or None when no valid JSON object is present.
    """
    text = re.sub(r"^```[a-zA-Z]*\s*", "", content.strip())
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def generate_story(
    topic: str,
    client: OpenAI,
    show_reasoning: bool = False
) -> Optional[Dict[str, Any]]:
    """Generate a murder case story, retrying once on failure.

    Args:
        topic: The story topic.
        client: DeepSeek client.
        show_reasoning: Whether to show reasoning.

    Returns:
        The generated case data as dict, or None on failure.
    """
    prompt = f"用户想要创建一个以「{topic}」为主题的剧本杀案件。\n\n{CASE_PROMPT_TEMPLATE}"

    logger.info("正在构思复杂案件...")
    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            content = generate_story_text(
                prompt, client, show_reasoning=show_reasoning
            )
        except RuntimeError as e:
            last_error = e
            logger.warning("故事生成调用失败（第 %d 次）: %s", attempt, e)
            continue

        data = extract_story_json(content)
        if data is not None:
            return data

        last_error = RuntimeError("模型输出中没有可用的JSON对象")
        logger.warning("故事生成解析失败（第 %d 次），重试中…", attempt)

    logger.error("故事生成最终失败: %s", last_error)
    return None


def parse_case_to_archive(
    case_data: Dict[str, Any],
    topic: str
) -> StoryArchive:
    """Convert generated case data to StoryArchive.

    Args:
        case_data: The generated case dictionary.
        topic: The original topic.

    Returns:
        StoryArchive instance.
    """
    # Convert characters
    characters = []
    for char_dict in case_data.get("characters", []):
        if not isinstance(char_dict, dict) or "id" not in char_dict:
            raise ValueError("角色数据缺少 id 字段")
        character = ScriptCharacter(
            id=char_dict["id"],
            name=char_dict["name"],
            public_identity=char_dict.get("public_identity", ""),
            secret=char_dict.get("secret", ""),
            is_killer=char_dict.get("is_killer", False),
            clues=char_dict.get("clue_ids", []),
            alibi=char_dict.get("alibi", ""),
            dialogue_style=char_dict.get("dialogue_style", ""),
            backstory=char_dict.get("backstory", ""),
            relationship_with_victim=char_dict.get("relationship_with_victim", ""),
            motive=char_dict.get("motive", ""),
            appearance=char_dict.get("appearance", "")
        )
        characters.append(character)

    # Convert clues
    clues = []
    for clue_dict in case_data.get("clues", []):
        if (
            not isinstance(clue_dict, dict)
            or "id" not in clue_dict
            or "content" not in clue_dict
        ):
            raise ValueError("线索数据缺少 id/content 字段")
        raw_content = clue_dict["content"]
        clean_content = raw_content.strip().rstrip("...").rstrip("。").rstrip("，").strip()

        clue = ClueData(
            id=clue_dict["id"],
            content=clean_content,
            type=clue_dict.get("type", "physical"),
            holder_id=clue_dict.get("holder_id", "scene"),
            reveal_to_all=clue_dict.get("reveal_to_all", False),
            required_clue_id=clue_dict.get("required_clue_id")
        )
        clues.append(clue)

    # Convert case
    victim_data = case_data.get("victim", {})
    case = CaseData(
        title=case_data.get("title", "未命名案件"),
        background=case_data.get("background", ""),
        victim=victim_data.get("name", "未知"),
        crime=f"{victim_data.get('name', '受害者')}被害",
        true_killer=case_data.get("true_killer_id", ""),
        motive="详见真相",
        location=case_data.get("location", ""),
        time=case_data.get("time", "")
    )

    archive = StoryArchive(
        id=StoryArchive.generate_id(),
        created_at=StoryArchive.generate_timestamp(),
        topic=topic,
        title=case_data.get("title", "未命名案件"),
        case=case,
        characters=characters,
        clues=clues,
        story_content=case_data.get("truth", "")
    )

    return archive


# ============ Storage Management ============

STORIES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "stories")


def ensure_stories_dir() -> None:
    """Ensure stories directory exists."""
    if not os.path.exists(STORIES_DIR):
        os.makedirs(STORIES_DIR)


def save_story(archive: StoryArchive) -> str:
    """Save story to JSON file.

    Args:
        archive: StoryArchive to save.

    Returns:
        Path to the saved file.
    """
    ensure_stories_dir()
    file_path = os.path.join(STORIES_DIR, f"{archive.id}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(archive.to_dict(), f, ensure_ascii=False, indent=2)

    logger.info("故事已保存: %s", file_path)
    return file_path


def load_story(story_id: str) -> Optional[StoryArchive]:
    """Load story from file.

    Args:
        story_id: The story ID.

    Returns:
        StoryArchive or None if not found.
    """
    file_path = os.path.join(STORIES_DIR, f"{story_id}.json")

    if not os.path.exists(file_path):
        logger.warning("存档不存在: %s", story_id)
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StoryArchive.from_dict(data)
    except Exception as e:
        logger.error("加载存档失败: %s", e)
        return None


def list_stories() -> List[Dict[str, Any]]:
    """List all saved stories.

    Returns:
        List of story info dictionaries.
    """
    ensure_stories_dir()
    stories = []

    for filename in os.listdir(STORIES_DIR):
        if filename.endswith(".json"):
            story_id = filename[:-5]
            archive = load_story(story_id)
            if archive:
                stories.append({
                    "id": archive.id,
                    "title": archive.title,
                    "topic": archive.topic,
                    "created_at": archive.created_at,
                    "num_characters": len(archive.characters)
                })

    return sorted(stories, key=lambda x: x["created_at"], reverse=True)


def delete_story(story_id: str) -> bool:
    """Delete a story.

    Args:
        story_id: The story ID.

    Returns:
        True if deleted.
    """
    file_path = os.path.join(STORIES_DIR, f"{story_id}.json")

    if not os.path.exists(file_path):
        logger.warning("存档不存在: %s", story_id)
        return False

    try:
        os.remove(file_path)
        try:
            delete_story_portraits(story_id)
        except Exception as e:
            # The archive is already deleted; a leftover image directory must
            # not turn that successful deletion into an API failure.
            logger.warning("删除故事肖像失败（%s）: %s", story_id, e)
        logger.info("已删除存档: %s", story_id)
        return True
    except Exception as e:
        logger.error("删除失败: %s", e)
        return False


# ============ High-level Service ============

class StoryService:
    """Story generation and management service."""

    def __init__(self):
        """Initialize the service."""
        ensure_stories_dir()
        self.portrait_service = PortraitService()

    def create_story(
        self,
        topic: str,
        show_reasoning: bool = False
    ) -> Optional[StoryArchive]:
        """Generate and save a new story.

        Args:
            topic: The story topic.
            show_reasoning: Whether to show DeepSeek reasoning.

        Returns:
            StoryArchive or None on failure.
        """
        client = create_deepseek_client()
        case_data = generate_story(topic, client, show_reasoning)

        if not case_data:
            return None

        try:
            archive = parse_case_to_archive(case_data, topic)
        except (KeyError, TypeError, ValueError) as e:
            logger.error("案件数据结构不完整: %s", e)
            return None

        # Portrait generation is non-fatal: a provider timeout still leaves a
        # fully playable story with letter-avatar fallbacks.
        self.portrait_service.generate_for_archive(archive)
        save_story(archive)

        return archive

    def get_story(self, story_id: str) -> Optional[StoryArchive]:
        """Load a story by ID.

        Args:
            story_id: The story ID.

        Returns:
            StoryArchive or None.
        """
        return load_story(story_id)

    def get_all_stories(self) -> List[Dict[str, Any]]:
        """Get all saved stories.

        Returns:
            List of story info.
        """
        return list_stories()

    def remove_story(self, story_id: str) -> bool:
        """Delete a story.

        Args:
            story_id: The story ID.

        Returns:
            True if deleted.
        """
        return delete_story(story_id)
