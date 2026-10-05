# 剧本结构与推理评审

## 当前契约与资料入口

以正在修改的仓库代码为准，不把本文件当作冻结的 schema。需要定位时先用 CodeGraph 查 `parse_package`、`StoryArchive.validate`、`validate_quick_evidence_routes`。

| 入口 | 用途 |
| --- | --- |
| `backend/app/domain/models.py` | CaseData、ScriptCharacter、ClueData、StoryArchive 及逐字引用校验 |
| `backend/app/services/story_catalog.py` | 包解析、人数、公开元数据、离线加载 |
| `backend/app/domain/game_manager.py` | 三轮证据可达性和真实搜证规则 |
| `backend/app/content/stories/manifest.json` | 明确列出的官方源码包 |
| `docs/story-library.md` | 导入、角色数、版本隔离 |
| `docs/original-cases-2026-10.md` | 现有原创设计及其未完成的真实体验验证 |

现有包只作为结构参考，不复制另一案件的情节、引用或制作结果。用户指定参考经典侦探小说时，使用封闭场景、有限嫌疑人、误导证言、公平线索等叙事方法；人物、关系、具体作案方法和结局独立创作。不要把换人名的改编宣称为原创。确需历史/技术/第三方事实时查可靠来源，记录来源；这些作者资料不进入角色上下文。

## 从主题到案件

先写一份简洁的作者设计记录，覆盖以下相互关联的信息，而不是给玩家直接展示真相：

1. 公开开场：玩家为何在场、何时发现事件、有限嫌疑人范围、马上可调查的方向。
2. 完整真实时间线：死亡、准备、实施、发现的时间分开；每人的位置、目击边界与接触机会相互一致。
3. 唯一致死者：动机、实际实施行为、本人知情、掩饰说辞分别确定。多名嫌疑人不等于多名真正致死者，当前引擎不支持需要多人同时指认的结局。
4. 推理闭环：正向识别依据与逐个排除依据；关键结论必须能从玩家得到的证据推导，不靠终局新增事实或 AI 主动自曝。
5. 三轮体验：第一轮建立可行动疑点，第二轮校正误导并交叉核对，第三轮收束定案。每轮给出新的调查收益，不让开场就直接写明凶手。
6. 每人的扮演价值：利益、隐瞒、可回答的亲历信息、独立任务和语言风格。人数依据这些职责选择，不为凑人数增加空角色。

主因果应在普通问答中可被追问，例如“你当时亲眼看到了什么”“这份记录能覆盖哪段时间”“这条痕迹为什么能排除别人”。不靠模型临场编造人物记忆。

## 数据包字段

顶层使用 `format_version=1`，必有 `metadata` 与 `archive`；配图使用顶层 `artwork`。

| 字段 | 写作约束 |
| --- | --- |
| metadata.schema_version / version | 当前格式1；内容版本为正整数，与目录修订号是不同计数器 |
| summary / difficulty / estimated_minutes | 无谜底简介，最多300字；难度最多20字；5—600分钟，时长是估计 |
| author / license / release_notes | 真实归属和仓库当前许可；版本说明不能伪称已真实审稿或已实玩 |
| archive.id / created_at / topic / title | 标准 UUID、真实创建时间、用户主题、中文标题 |
| case | title、background、victim、crime、true_killer、motive，另有 location/time；background/crime 可公开，不能夹带作者答案 |
| characters | 3—8名，ID/姓名唯一；true_killer 指向一人，原始 is_killer 标记与其一致 |
| clues | 3—60条，ID唯一；type 为 physical/testimony/document；holder_id 是 scene 或实际角色ID |
| story_content | 作者全知的完整正文，不作为角色公开开场 |
| solution | 每项严格含 conclusion、evidence；每个引用严格含 clue_id、quote，quote 必须逐字出现在对应 content 内 |
| production / catalog | 不手写虚假的线上通过记录；公开 metadata 由可信加载器派生为 catalog |

每个角色写 `public_identity`、`public_introduction`、`appearance`、`dialogue_style`，以及其本人知识 `self_knowledge` 和非空 `objectives`。`secret/backstory/alibi/relationship_with_victim/motive` 按当前类型完整填写，但这些作者字段不能代替本人知识。

`self_knowledge` 用第一人称陈述自己做过、见过、明确被告知的事。凶手必须明确知道自己的真实实施行为；无辜者不拥有未目睹的行凶真相。`cover_story` 只写角色打算对外声称的内容，不当作事实。未知保留未知，模糊目击保留不确定。私密目标不要求无辜者无限否认已公开证据证实的亲历事实。

每条线索写中文 `content`、无谜底调查入口 `lead`、`discovery_round=1/2/3` 和可选 `required_clue_id`。依赖不能指向不存在、较晚轮次或形成环。原稿 `reveal_to_all=false`；角色 `clues` 只列该人实际持有的线索，不能列 scene 或别人的资料。

每轮应有可调查的场景证据。当前回归要求所有官方案件的 authored clues 能在完整调查中公开取得，新增本优先沿用 scene 为关键证据的设计；如果确需个人证据，先验证所有非凶手角色都能取得定案所需证据，不假设 NPC 自动公开私藏资料，也不删除现有可达性测试绕过问题。

## 语义复核与制作记录

对每项 solution 逐字检查引用后，再判断引用是否真的支持结论。重点检查：动机不等于实施、普通相似物不等于唯一匹配、事故时间不等于准备时间、局部在场不等于整段在场、证言不是自动成立的事实、不知道某事不等于知道没发生。逐人尝试另一个解释，确认现有证据能排除该解释，而不是只因作者指定了真凶。

把修改点、来源、验证和未完成项目记在 `docs/` 的本批制作记录中。自检只能称作者自检。`parse_package` 会把制作来源置为本地结构/可达性状态，不认证包自称的“精品”或“审稿通过”。

需要且获准做真实模型审稿时，复用 `story_service.py` 的现有审稿契约：负面结果修稿，正面结果需核对实际致死者 ID 与该角色本人作案原文；结构与证据修补按字段保留ID、限次并复查。不要绕过身份核对或把一次笼统“可以”写成通过。已经生成好的成品开局不再触发审稿、生图；制作评审只发生在新稿/新修订的交付阶段。

真实实玩需要覆盖调查、定向质问与出示证据、指认、揭晓，记录模型与体验问题；不能把假模型流程或只打开序幕称作真实模型完整游玩。使用临时测试目录，不覆盖用户档案。项目真实 key 只在原有本地配置内使用，不打印或写进制作记录。

## 验证命令

以下命令从仓库执行，选择已安装依赖的 Python；图像工具另需 Pillow。

```bash
python3 <skill-dir>/scripts/story_tools.py check --repo . --package <draft.json> --draft
python3 <skill-dir>/scripts/story_tools.py check --repo .
cd backend
python -m pytest tests/test_story_catalog.py tests/test_story_playability.py tests/test_story_content_service.py -q
```

新增案件可能影响 `test_story_catalog.py` 的目录人数数组及制作记录的组合计数，需要按 manifest 的实际新增内容更新期望。保留逐角色、双模式、冻结存档和离线资源校验。若变更影响引擎/状态机，应遵守仓库相应代码检查要求；普通创作不应重写引擎。

Android共享层可验证，但每次内容更新不需重建 APK：

```bash
python3 scripts/stage-android-python.py
PYTHONPATH=frontend/android/app/build/generated/python python3 -S mobile_engine/tests/test_mobile_runtime.py
python3 scripts/tests/test_story_publisher.py
```

手机测试目前含基础三本与指定下载本的夹具；新增故事需补充实际新增包覆盖，不能仅引用旧的6项通过就称新案件已被手机测试。`story_tools.py check` 只证明当前包结构、三轮可达性和可选图片解码；不验证推理语义、缓存命中率或真实模型表现。
