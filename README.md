<img src="frontend/public/brand/logo-casefile-v2.png" width="72" height="72" alt="剧本杀 Logo" />

# 剧本杀 - Murder Mystery Game

![Art Deco Noir Style](https://img.shields.io/badge/Style-Art%20Deco%20Noir-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge)
![Tests](https://img.shields.io/badge/Tests-regression%20suite-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/License-AGPL%203.0--only-green?style=for-the-badge)

一个基于 OpenAI 兼容大模型 API 的 AI 剧本杀游戏。玩家可以与 AI 角色进行实时对话、调查线索、讨论案情、指认凶手，体验完整的剧本杀游戏流程。

安卓独立运行预览版可直接下载安装：游戏引擎、SQLite 存档、精选剧本和配图均在手机本地，模型请求由手机直接发送。**APK 不内置 API key，安装后请在「模型设置」填写自己的密钥；无需电脑或自建服务器。** AI 对话和自行生成剧本需要联网，并消耗所配置供应商的 API 额度。

移动界面已修复键盘返回、通知安全区、小屏聊天、案情字段显示及指认弹窗，验证范围见 [UI 适配记录](docs/android-ui-audit.md)。

## 📱 安卓下载与使用

当前发布：**1.0.0-preview.3**（versionCode 16，开发签名，arm64-v8a，Android 7.0 / API 24 及以上）。本版加入独立剧本更新，精选库可检查目录、下载/更新、取消重试及安装官方离线包。APK 保留三个基础本，另有三个原创文字本体验预览可单独下载；同签名覆盖安装保留手机配置和存档。

- [下载 APK：Murder-Mystery-1.0.0-preview.3-arm64.apk](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/download/v1.0.0-android-preview.3/Murder-Mystery-1.0.0-preview.3-arm64.apk)
- [发布说明与校验文件](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/tag/v1.0.0-android-preview.3)

1. 在手机打开下载链接，安装 APK；系统要求时允许浏览器安装此应用。
2. 打开「模型设置」，填写自己的 OpenAI 兼容 HTTPS 服务地址、API key 和模型名称。默认提供 DeepSeek 配置，也可按所用服务调整三个模型名称。
3. 在「精选剧本 → 已下载」直接开始游玩；到「发现新本」检查目录并下载更多案件，下载不需要模型密钥。预制内容开局只做本地检查，**不重新生成故事、审稿或生图**；AI 对话仍需有效密钥与网络。
4. 也可在「生成新剧本」输入主题，自动决定人数或指定 3—8 人。生成会经过模型审稿与必要修补，耗时和质量受模型影响，推荐先体验精选本。
5. 离开游戏后可从首页继续，结案后可打开本地复盘。卸载应用会删除本地存档和配置；覆盖更新需使用相同签名。

密钥通过手机原生设置输入，由 Android Keystore 管理的密钥加密保存，不进入 WebView、Python 提示词或游戏存档。发布 APK 按源码白名单构建，检查外层 APK 和内嵌 Python 归档，排除电脑 `.env`、真实密钥、用户数据库、存档和日志。首次安装为空配置；覆盖安装会保留玩家此前在手机填写的密钥。

这是可安装的开发预览版，应用 ID 为 `com.murdermystery.game.debug`，尚未作为正式商店版本发布。目前仅发布 64 位 ARM 包；真机流程验收基于 Redmi / Android 16，其他机型尚未全部验证。内置头像可离线显示，**安卓版自行生成剧本的 DashScope 在线生图尚未接入**。

## 📖 内置原创剧本

当前源码与官方内容目录包含六个原创故事。`1.0.0-preview.3` APK 包含首批三个基础本及其 3 张封面、15 张人物头像，另三个本通过签名包下载；以后兼容的内容更新无需再构建 APK。旧 preview.2 需先覆盖升级一次。新增本的3张场景封面通过content-r2内容包提供，人物使用姓名头像，不在开局时请求生图。

| 剧本 | 角色数（含玩家） | 内容版本 |
|------|:---:|:---:|
| 雨夜的最后一声钟 | 3 | 2 |
| 白鹭旅馆的无字药瓶 | 5 | 1 |
| 雾港双重提货单 | 7 | 1 |
| 玻璃花房的空白铭牌 | 4 | 1 |
| 潮汐之前的晚宴 | 6 | 1 |
| 终场之前的返场 | 8 | 1 |

精选本为项目原创内容。新增批次参考经典侦探小说的封闭场景、多方动机、证词校正与公平推理方法，人物、具体情节和证据链独立创作，详见 [新增剧本记录](docs/original-cases-2026-10.md)。剧本库通过 manifest 和版本化 JSON 数据包扩展，Android preview.3 通过受信签名内容包扩展；个人 JSON 仍进入“我的剧本”，Web 后端读取源码清单。新开局读取新版本，已开局存档冻结自己的剧本正文。包格式见 [剧本库说明](docs/story-library.md)，配图与更新规则见 [配图记录](docs/story-artwork.md)。

preview.3 采用“APK 基础本 + 可下载内容包”：首页精选库增加“已下载／发现新本”、检查更新、下载/取消/重试、离线签名包安装；下载不需要模型密钥，失败不阻塞本地故事。新增故事和配图可独立交付，只有引擎或界面升级才需更换 APK。新版本与旧局的正文、人物和历史图片隔离；不重新审稿或开局生图。首个目录 [content-r1](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/tag/content-r1) 包含六个签名包，更新契约与真机验收边界见 [剧本内容独立更新](docs/story-content-updates.md)。

## ✨ 功能特点

### 🎯 核心功能
- **玩家角色** - 新开局只分配非凶手角色，玩家以找出真凶为目标
- **AI 角色扮演** - 每个角色都有独特的对话风格、隐藏秘密与凶手伪装策略
- **AI 剧本生成** - 输入任意主题，AI 自动生成完整剧本（人物、线索、真相）
- **人物配图** - 首批精选本内置封面与人物头像，新增文字本使用案卷与姓名头像（体验预览，真实模型及玩家评审尚未完成）；电脑版可选配置 DashScope 为新稿生成肖像
- **完整游戏流程** - 自我介绍 → 搜证 → 讨论 → 投票 → 真相揭晓
- **⚡ 实时流式对话** - SSE 流式输出，AI 角色边生成边显示
- **角色剧本** - 玩家与 AI 使用各自的本人知识、案发行动和任务，作者真相不直接下发
- **上下文感知** - 按角色权限冻结资料，区分案情、线索和证言，保留带来源的长期记忆并校验回复
- **定向质问** - 选择询问对象并出示已掌握证据；出示后成为公开证据，无辜角色应承认证据证实的相关经历

### 🔍 搜证系统
- **三类线索** - 物证（Physical）、证词（Testimony）、文书（Document）
- **主动搜证** - 搜证阶段点击「搜证」按钮随机获得新线索
- **线索解锁链** - 部分线索需先获得前置线索才会出现
- **线索详情** - 点击查看完整线索内容

### 💬 讨论系统
- **实时对话** - 与 AI 角色进行自然语言交流
- **⚡ 并发响应** - 多个 AI 角色并行生成，玩家无需串行等待
- **SSE 流式输出** - 每个角色的回复独立推送，边生成边渲染
- **多轮讨论** - 支持多个讨论回合，完整历史跨阶段保留
- **返回搜证** - 讨论中途可返回搜证获取新线索（讨论记录保留）

### ⚖️ 指认与投票
- **指认凶手** - 随时可以指认凶手（每局只有一次机会）
- **最终结案** - 单人游戏按玩家的最终选择判定胜负，确认后本地保存并立即揭晓，AI 判断按需生成供复盘参考
- **模型失败** - 可选人物判断失败时弃权；不阻塞玩家结案、不随机投票，揭晓后禁止改写结果

### 💾 会话持久化
- **进程重启不丢失** - 安卓自动保存到本地 SQLite；Web 后端可选 JSON 文件存档
- **可插拔存储** - 默认内存存储；设 `SESSIONS_DIR` 即启用文件持久化
- **自动恢复** - 启动时自动加载已保存的会话

### 🎨 界面特色
- **Art Deco Noir 风格** - 奢华金色 + 深邃黑色配色
- **流畅动画** - 精心设计的微交互和过渡动画

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React 19)                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ Homepage │  │Investi-│  │Discuss- │  │  Vote   │    │
│  │          │  │  gation │  │  ion    │  │          │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │         │
│       └──────────────┴──────┬───────┴──────────────┘         │
│                              │                                │
│                              ▼                                │
│                    ┌─────────────────────┐                    │
│                    │   Vite Dev (5173)   │  ← 动态端口代理    │
│                    │   读 .port.json     │                    │
│                    └─────────┬───────────┘                    │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              后端 FastAPI (动态端口 8000+)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           app/api/  — HTTP 层（薄）                   │   │
│  │  endpoints/games.py    (创建/加载/动作)               │   │
│  │  endpoints/stories.py  (列出存档)                     │   │
│  │  dependencies.py       (FastAPI Depends 注入)         │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │     app/services/session_service.py — 业务逻辑         │   │
│  │  GameSession      单一游戏运行时                       │   │
│  │  SessionManager   注册表 + 持久化（Protocol）          │   │
│  │  InMemory / JsonFile SessionStore                     │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │   app/domain/  — 纯逻辑                                │   │
│  │  game_manager.py    阶段/投票/指认/线索                 │   │
│  │  models.py          数据模型（dataclass）              │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │   app/agents/  — AI 角色                              │   │
│  │  roleplay_character.py  V4-Flash 角色扮演             │   │
│  │  story_service.py    DeepSeek 剧本生成 / 存档 / 肖像调度 │   │
│  │  image_service.py    Qwen Image 肖像生成与本地持久化    │   │
│  └──────────────────────┬───────────────────────────────┘   │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │   LLM API              │
                │ DeepSeek V4 + Qwen Image │
                └────────────────────────┘
```

## 🎮 游戏流程

```
                    ┌─────────────────┐
                    │   1. 创建游戏   │
                    │  (输入剧本主题)  │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    2. 自我介绍阶段                        │
│         每个角色依次进行自我介绍，揭示公开身份              │
└─────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    3. 搜证阶段 🔍                         │
│    • 查看个人线索                                          │
│    • 点击线索查看详情                                       │
│    • 可随时进入讨论或指认                                   │
└─────────────────────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│    4a. 讨论阶段 💬       │   │    4b. 指认凶手 ⚡       │
│ • AI 角色并行响应         │   │  (每局仅一次机会!)        │
│ • SSE 流式边收边显示      │   │  • 选择嫌疑人             │
│ • 分享线索信息            │   │  • 确认指认               │
│ • 进入投票                │   │  • 正确→好人胜利         │
└─────────────┬───────────┘   │  • 错误→凶手逃脱         │
              │                 └─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                    5. 投票阶段 🗳️                        │
│              玩家选择凶手，确认后立即结案                   │
│    • 确认→保存判断并揭示真相                              │
│    • 人物表决意见可选，不改变玩家判定                      │
└─────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    6. 真相揭晓 🔮                         │
│         • 公布正确答案                                     │
│         • 显示凶手身份和动机                                │
│         • 展示完整故事背景                                  │
└─────────────────────────────────────────────────────────┘
```

## 🚀 电脑 Web 开发与运行

以下环境与 `.env` 仅用于电脑运行 Web 后端，安装安卓 APK 不需要这些步骤。

### 环境要求

- **Python**: 3.11+
- **Node.js**: 22+
- **包管理器**: pip, npm

### 1. 克隆项目

```bash
git clone https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game.git
cd Murder-Mystery-Game
```

### 2. 配置 API 密钥

本项目需要 LLM API 密钥来驱动 AI 角色；若启用自动人物肖像，还需要 DashScope API 密钥。

默认使用 **DeepSeek V4 Pro**（故事生成和审稿，低强度思考）+ **DeepSeek V4 Flash**（角色扮演，默认关闭额外思考），单一供应商、一个 API key 即可。

密钥存放在 **`backend/.env`**（相对路径以 `backend/` 为基准解析，与启动目录无关）；该文件被根目录 `.gitignore` 忽略，不应提交，也不会由安卓构建白名单复制到 APK。

```bash
# 进入后端目录
cd backend

# 复制环境变量模板（模板含全部变量与注释）
cp .env.simple .env

# 编辑 .env，填入你的密钥
# Linux/Mac:
nano .env
# Windows:
notepad .env
```

`.env` 文件关键配置（完整列表见 `.env.simple`）：

```env
# 故事生成（V4 Pro，思考模式默认开启）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro

# 角色扮演（V4 Flash，思考模式默认关闭以保证低延迟；不设 key 时自动复用 DEEPSEEK_API_KEY）
ROLEPLAY_MODEL=deepseek-v4-flash

# 人物肖像（DashScope 原生 API；不配置时仍使用首字母头像）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
DASHSCOPE_IMAGE_MODEL=qwen-image-3.0
```

> 💡 **获取 API 密钥**: DeepSeek: https://platform.deepseek.com/；DashScope: https://platform.qianwenai.com/
>
> ⚠️ **快速失败**：启动时若 `DEEPSEEK_API_KEY` 缺失，后端会直接报错退出（fail fast），而不是在游戏中途抛出晦涩的 401。检查 `.env` 环境变量是否配置正确即可。
>
> 🖼️ **肖像存储**：载入时核对本地文件，失效 URL 回退为首字头像。只有新剧本制作后才调度画像生成；成品开局、列表和恢复旧会话不发起图片生成。后台只合并肖像字段，不覆盖期间的剧情编辑或恢复已删除剧本。

> 新剧本会为每个角色并发生成一张 2:3 肖像，成功图片立即下载到 `backend/assets/portraits/<剧本ID>/`，并将访问路径写入该剧本 JSON。DashScope 密钥缺失或单张失败时，剧本仍可正常创建，并回退为首字母头像。

### 3. 安装依赖 + 启动

**方式 A：一键（推荐）** — 在项目根目录直接：

```bash
# 首次：安装所有依赖（前端 + 后端 pip 提示）
npm run install:all
pip install -r backend/requirements.txt   # 后端依赖

# 启动前后端
npm run dev
```

**方式 B：使用平台脚本**（效果相同）

```bash
./start.sh        # Git Bash / Linux / Mac
start.bat         # Windows CMD
powershell start.ps1   # Windows PowerShell
```

打开浏览器访问: **http://localhost:5173**

1. 从首页「精选剧本」选择现成案件，或进入「生成新剧本」自行制作。
2. 选择速推或经典模式，开始游戏。
3. 系统分配一个非凶手角色，阅读本人资料后搜证与对质。
4. 完成调查、选择最终指认，查看真相与复盘。

### 速推模式

新建案件时可以选择“速推模式”或“经典模式”：

- 速推模式固定 3 轮调查；证据按 `discovery_round` 分轮解锁，每轮可选择具体地点或物件调查，不能第一轮搜完后续证据。
- 经典模式保留自由调查和原有随机搜证流程，适合更完整的沉浸式体验。
- 速推模式每轮至少主动调查一次并发表一次推论，完成全部 3 轮后才能进入投票。线索耗尽时免除调查要求，仍需发言；查看案卷和补查不推进轮次，完成本轮后用「下一轮调查」明确推进。
- 最后一轮也可以返回搜证补查，轮次保持为 3；确认最终选择后立即结案，AI 分票或弃权不阻止结案。
- Web 刷新会恢复已保存的自我介绍和胜负结果；小程序开局、阶段切换及轮询会同步线索和讨论。

> 💡 `npm run dev` 脚本会自动：
> - 检测 Python / Node 依赖是否就绪（缺则打印修复命令并退出）
> - 后端先启动，**等端口文件写入完成再起前端**（避免 Vite 代理竞态）
> - 跨平台统一：Windows / Mac / Linux 行为一致
> - `Ctrl+C` 干净停掉两个服务

### 4. 其他 npm 脚本

| 脚本 | 作用 |
|---|---|
| `npm run dev` | **同时启动前后端**（推荐） |
| `npm run dev:backend` | 只起后端 |
| `npm run dev:frontend` | 只起前端 |
| `npm run install:all` | 安装根 + 前端依赖 |
| `npm run test:backend` | 跑后端 pytest |

## ⚙️ 配置

完整环境变量（参考 `backend/.env.simple`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | 故事生成 + 角色扮演必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek 端点 |
| `DEEPSEEK_MODEL` | `deepseek-v4-pro` | 故事生成模型（原稿/审稿开启低强度思考；修补关闭） |
| `ROLEPLAY_API_KEY` | 复用 `DEEPSEEK_API_KEY` | 角色扮演密钥（可选，通常不设） |
| `ROLEPLAY_BASE_URL` | 复用 `DEEPSEEK_BASE_URL` | 角色扮演端点（可选） |
| `ROLEPLAY_MODEL` | `deepseek-v4-flash` | 角色扮演模型（思考模式关闭） |
| `ROLEPLAY_TEMPERATURE` | `1.0` | 角色生成温度（思考模式下无效） |
| `ROLEPLAY_TOP_P` | `0.95` | 角色生成 top_p（思考模式下无效） |
| `ROLEPLAY_MAX_TOKENS` | `2048` | 角色生成最大 token |
| `ROLEPLAY_REVIEW_MODEL` | DeepSeek 官方端点为 `deepseek-v4-pro`，其他端点复用扮演模型 | 独立事实审查模型，使用扮演端点与密钥 |
| `ROLEPLAY_CONTEXT_TOKEN_BUDGET` | `12000` | 输入上下文的保守估算预算，包含工具定义与重试余量 |
| `ROLEPLAY_THINKING_ENABLED` | `false` | 角色扮演是否开思考模式 |
| `DASHSCOPE_API_KEY` | — | Qwen Image 人物肖像密钥（可选） |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/api/v1` | DashScope 原生 API 端点 |
| `DASHSCOPE_IMAGE_MODEL` | `qwen-image-3.0` | 人物肖像文生图模型 |
| `DASHSCOPE_IMAGE_SIZE` | `1024*1536` | 肖像输出尺寸（宽*高） |
| `DASHSCOPE_IMAGE_MAX_WORKERS` | `2` | 同时生成的肖像数，兼顾限流与成本 |
| `DASHSCOPE_IMAGE_TIMEOUT_SECONDS` | `150` | 单张肖像任务的总超时秒数 |
| `CORS_ALLOWED_ORIGINS` | localhost dev | 逗号分隔；不设则只允许本地 |
| `LOG_LEVEL` | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `SESSIONS_DIR` | — | 不设则内存存储；设了启用 JSON 持久化。相对路径以 `backend/` 为基准（如 `sessions`） |

## 📚 API 文档

启动服务后访问: **http://localhost:8000/docs**

### 主要接口

| 方法 | 端点 | 描述 |
|:---:|------|------|
| `GET` | `/stories` | 获取剧本列表 |
| `POST` | `/games` | 创建新游戏 |
| `POST` | `/games/load` | 从已有故事加载游戏 |
| `GET` | `/games/{id}` | 获取游戏状态 |
| `GET` | `/games/{id}/clues` | 获取线索列表 |
| `POST` | `/games/{id}/introduce` | 提交自我介绍（body 传 `message`，返回全部 AI 介绍） |
| `POST` | `/games/{id}/investigate` | **主动搜证**；速推模式可传 `{"lead_id": "..."}` 选择调查方向 |
| `POST` | `/games/{id}/speak` | 发送发言（批式，所有 AI 回复一次返回） |
| `POST` | `/games/{id}/speak/stream` | **发送发言（SSE 流式，AI 完成一个推送一个）** |
| `POST` | `/games/{id}/accuse` | 指认凶手 |
| `POST` | `/games/{id}/vote` | 本地保存玩家最终选择并立即结案，不调用模型 |
| `POST` | `/games/{id}/ballot-advice` | 结案后按需生成角色判断，复用揭晓前的权限视图 |
| `POST` | `/games/{id}/next-investigation-round` | 完成本轮后开启下一轮速推调查 |
| `POST` | `/games/{id}/start-voting` | 进入投票阶段 |
| `POST` | `/games/{id}/return-to-investigation` | 返回本轮补查，不增加速推轮次 |
| `GET` | `/games/{id}/reveal` | 获取真相揭示 |
| `GET` | `/games/{id}/discussion-history` | 讨论历史 |

状态接口中的 `game_id` 是本局会话 ID，`story_id` 是剧本 ID；同时返回 `game_ended`、`winner` 和 `is_speaking`。阶段、搜证及普通发言响应中的 `available_actions` 用于同步客户端按钮条件。

`/speak` 与 `/speak/stream` 支持可选 `target_id`、`presented_clue_ids` 和 UUID 格式 `action_id`。只能出示本人已掌握或已公开的线索；定向询问只调用该角色，默认仍为全员讨论。

玩家载荷新增 `role_script`、`objectives`，仅玩家本人资料包含这些字段。揭晓载荷提供 `player_verdict`、`deductions`（终局证据原文与是否发现）、`advice_state` 和 `votes`，刷新后仍可查看。

`/reveal` 只在游戏结束并进入揭晓阶段后开放。投票阶段不能通过 `/next-phase` 跳过计票；角色回应期间，新的发言、指认或阶段切换返回 `409`，请等待当前回应完成。

SSE 断开后，本轮 AI 回复仍在后台完成并写入讨论记录和会话存档。客户端恢复时通过状态与讨论历史接口获取后续回复；没有收到 `done` 就结束的流按中断处理。文件存档通过原子替换写入，避免读取半份 JSON。

### SSE 流式响应示例

```bash
curl -N -X POST http://localhost:8000/games/{id}/speak/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "我觉得 Alice 很可疑"}'
```

事件流先推送已记录并保存的玩家问题，再逐个推送经过检查的 AI 回应；客户端收到问题后才清除草稿，不重复乐观回显：

```
event: message
data: {"speaker": "玩家", "message": "问题原文", "action_id": "本次提交标识", "kind": "question"}

event: message
data: {"speaker": "Bob", "message": "...", "action_id": "本次提交标识", "kind": "statement"}

event: message
data: {"speaker": "Carol", "message": "..."}

event: done
data: {"phase": "discussion"}
```

## 🛠️ 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| [FastAPI](https://fastapi.tiangolo.com/) | Web 框架（薄路由层） |
| [Pydantic](https://docs.pydantic.dev/) | 数据验证 / 配置 |
| [OpenAI SDK](https://github.com/openai/openai-python) | V4-Pro / V4-Flash 客户端（OpenAI 兼容） |
| [DeepSeek](https://platform.deepseek.com/) | 剧本生成与角色扮演模型 |
| [Qwen Image](https://platform.qianwenai.com/docs/developer-guides/image-generation/text-to-image) | 角色肖像文生图（DashScope 原生 API） |
| [pytest](https://docs.pytest.org/) | 单元测试 |
| [uvicorn](https://www.uvicorn.org/) | ASGI 服务器 |

### 前端
| 技术 | 用途 |
|------|------|
| [React 19](https://react.dev/) | UI 框架 |
| [TypeScript](https://www.typescriptlang.org/) | 类型安全 |
| [Vite 8](https://vitejs.dev/) | 构建工具（自动端口代理） |
| [React Router 7](https://reactrouter.com/) | 路由管理 |
| [Lucide React](https://lucide.dev/) | 图标库 |

## 🔧 开发指南

### 构建安卓 APK

准备 Node.js 22+、JDK 21、Android SDK 36、Python，并设置 `JAVA_HOME` 和 `ANDROID_HOME`。Chaquopy 在 APK 内提供 Python 3.11，玩家无需单独安装运行环境。

```bash
cd frontend && npm ci && cd ..
npm run android:apk
# APK: frontend/android/app/build/outputs/apk/debug/app-debug.apk
# 单独复查构建产物（包括 Chaquopy 嵌套归档）
python3 scripts/audit-android-apk.py frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

构建脚本先生成 Android 页面与本地配图，再按白名单打包游戏引擎和剧本，最后执行凭据与内容检查。检查会在内存中与本机 `backend/.env` 的密钥比对，输出仅含文件名和结果，不输出密钥。APK 作为 GitHub Release 附件发布，不加入 Git 源码。升级构建需保留原签名；具体签名与真机验收方法见 [安卓实施记录](docs/android-port-plan.md)。

### 项目结构

```
MurderMystery/
├── package.json              根级 npm 脚本
├── start.sh / .bat / .ps1    备用平台启动脚本
├── scripts/                  跨平台 Node 启动器（无依赖）
│   ├── dev.js                前后端并发启动
│   └── dev-backend.js        仅后端
├── backend/
│   ├── app/
│   │   ├── agents/           AI 角色代理
│   │   │   └── roleplay_character.py  角色生成、来源校验与一致性检查
│   │   ├── api/              HTTP 层（薄）
│   │   │   ├── dependencies.py   FastAPI Depends 注入
│   │   │   ├── endpoints/
│   │   │   │   ├── games.py      /games/* 路由
│   │   │   │   └── stories.py    /stories 路由
│   │   │   ├── routes.py         路由聚合
│   │   │   └── schemas.py        Pydantic 模型
│   │   ├── core/             基础工具
│   │   │   ├── config.py         配置（环境变量）
│   │   │   ├── logging.py        logging 配置
│   │   │   ├── phases.py         阶段枚举
│   │   │   ├── port.py           端口探测
│   │   │   └── prompts.py        Prompt 模板（含凶手策略）
│   │   ├── domain/           纯领域逻辑
│   │   │   ├── game_manager.py   阶段/投票/指认/线索解锁
│   │   │   └── models.py         数据模型
│   │   ├── services/         业务服务
│   │   │   ├── session_service.py  GameSession + SessionManager（全异步）
│   │   │   └── story_service.py    剧本生成与存档
│   │   ├── main.py           FastAPI 入口
│   │   └── cli.py            CLI 工具
│   ├── stories/              剧本存档
│   ├── tests/                pytest 单元测试
│   │   ├── conftest.py
│   │   ├── test_game_manager.py      游戏规则与线索测试
│   │   └── test_session_service.py   会话、持久化与速推模式测试
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              API 客户端（client.ts 含 SSE 解析）
│   │   ├── components/       按游戏阶段分目录
│   │   ├── context/GameContext.tsx  全局状态 + 流式消费
│   │   ├── pages/            HomePage / GamePage
│   │   └── styles/           Art Deco Noir 主题
│   ├── package.json
│   └── vite.config.ts        读 .port.json 配置代理
└── README.md
```

### 运行测试

```bash
# 后端：运行完整 pytest 测试集
npm run test:backend
# 或
cd backend && python -m pytest

# 前端类型检查
cd frontend && npx tsc --noEmit

# 单个文件
cd backend && python -m pytest tests/test_game_manager.py -v
```

Web 状态与 SSE 回归测试：`cd frontend && npm test`；小程序状态回归测试：`cd miniprogram && pnpm test`。

测试覆盖：终局保护、真相访问限制、非凶手玩家分配、断流后回复与存档一致性、速推实际调查/讨论轮次、最后一轮补查、刷新及跨局恢复、阶段转换、单人最终判定、AI 弃权与表决复盘、定向质问/证据出示、指认（对/错/限额/自我/淘汰目标）、线索分配与解锁链、淘汰、讨论历史、会话快照往返、JSON 持久化恢复等。

## ❓ 常见问题

**Q: 在 Windows 上 `npm run dev` 启动报 `'vite' 不是内部或外部命令`？**

A: 已修复。当前脚本用 `node node_modules/vite/bin/vite.js` 直接调用 Vite，绕开了 cmd.exe 的 PATH 问题。如仍报，请确认 `frontend/node_modules` 已安装（`npm run install:all`）。

**Q: 申请 API 密钥需要付费吗？**

A: AI 对话和生成使用你填写的供应商账户，通常按调用量收费；具体价格和额度以供应商控制台为准。安装 APK 不附赠密钥或 API 额度。默认分别配置故事生成、角色扮演和事实审查模型。

**Q: 游戏过程中 AI 响应很慢怎么办？**

A: 新案件需串行完成原稿、结构检查、证据审稿，若有矛盾还需修补和再审。官方 DeepSeek V4 原稿和审稿保留低强度思考（审稿总输出含思考预算为 12288 tokens），字段修补关闭额外思考并限制输出为 8192 tokens；重复的完整证据引用只在模型输入中去重，校验仍读取真实原文。手机显示实际任务阶段和用时。讨论阶段并发触发各角色，逐个完成后显示；游玩已保存的案件直接本地开局，完全不重复审稿；提交最终判断也不等待人物表决。

**Q: 重启后游戏状态会丢吗？**

A: 安卓版会自动保存到本地 SQLite，重启可继续。Web 后端默认内存存储会丢；在 `backend/.env` 设 `SESSIONS_DIR=sessions` 启用 JSON 持久化，启动时自动恢复。

**Q: 可以自定义剧本吗？**

A: 可以！剧本以 JSON 格式存储在 `backend/stories/` 目录。通过 `/games/load` 端点加载已有 story_id。

**Q: 支持多人联机吗？**

A: 当前每局只有一个人类玩家，其他角色由 AI 控制；尚未提供多人联机。

**Q: SSE 流式和普通 /speak 端点的区别？**

A: `/speak` 等所有 AI 完成后一次性返回；`/speak/stream` 用 Server-Sent Events 每完成一个 AI 角色就推一条 `message` 事件。流式失败时，前端通过讨论历史接口重新同步，避免重复提交消息。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目当前采用 **GNU Affero General Public License v3.0 only（AGPL-3.0-only）**，完整条款见 [LICENSE](LICENSE)。

- **允许商用**、修改和再分发，需遵守许可证。
- 分发本项目或其修改版（包括 APK）时，须按许可证向接收者提供对应源码；修改版通过网络让用户使用时，须向这些用户显著提供免费获取对应源码的入口。
- 仅在本地自用且不分发、不向网络用户提供修改版，不要求因此公开私人修改。源码提供义务不意味着公开 API key、用户存档或无关的独立系统。

许可变更从包含此变更的首个提交开始适用；此前已按 Apache 2.0 发布的版本保留原有授权，包括 `v1.0.0-android-preview.1`、`v1.0.0-android-preview.2`。第三方依赖和材料保留各自许可证。范围、版本边界与发布方式见 [许可说明](docs/licensing.md)。

## 🙏 致谢

- [DeepSeek](https://platform.deepseek.com/) - 提供 V4 Pro / V4 Flash LLM API
- 所有开源贡献者

---

⭐ 如果这个项目对你有帮助，请 star 支持一下！

### 剧本校验与旧存档

生成和载入会在本地校验角色/线索 ID、真凶、线索前置引用和循环依赖。新生成案件必须包含本人知识、任务、调查方向、三轮证据和作者侧 `solution` 证据映射（结论、线索 ID、逐字原文）；首稿最多生成两次，结构和证据一致性问题分别最多修补两次，每次重新校验，通过后才保存。在线审稿只发生于新制作，不在成品开局时重复。旧剧本缺省轮次会按依赖顺序分配；没有审核过的本人知识时仅展示公开身份，不自动复制可能泄露答案的作者备注。

现有 9 个剧本已补充个人剧本和轮次，修复孤岛的循环依赖、暗房线索的作者时间线剧透及已发现的证据矛盾。结构校验不等于完整的推理质量审稿；模型是否遵守证据响应规则仍需真实模型试玩。


### 角色上下文与证言

`ContextAssembler` 先筛选角色本人知识、任务、已获得或已公开的线索，再检索历史。完整公开案情包含受害者与案件描述；其他角色只提供公开身份，作者真相不进入扮演请求。定向询问仍是公共讨论，出示的证据对所有人公开。

一次行动中的所有 NPC 使用同一事件序号的不可变快照，本轮其他 NPC 的回复在下一次行动才可见。系统消息只放规则；资料与带说话人的发言作为数据提供，当前提问只出现一次。相同线索按 ID 去重并保留种类、归属和公开状态；文书、证词和角色发言不自动成为客观事实。

长期记忆从完整事件日志确定性选取原话，按问题相关性、重要证言、近期对话排序；更正与原话一起提供，不生成无来源的事实摘要。预算按 UTF-8 字节数保守估算，并非模型的精确 tokenizer；必要案情、本人知识和可见线索不会被静默截断。日志记录选中来源、因预算省略的可见事件、行动 ID、快照序号与估算用量。

模型上下文格式为 v3，序列化顺序固定为：公共案情 → 本角色资料与玩家身份 → 可见线索 → 按原始顺序排列的证言 → 当前阶段、轮次、公开线索 ID、引用白名单 → 本次提问。阶段规则和工具定义保持固定，动态候选人与来源白名单放入上下文，由后端再次校验。线索从私有变为公开只更新末尾的 `public_clue_ids`，不改写线索正文。角色自我介绍仍不包含本人私密知识；发言和独立审查分别使用稳定前缀。

历史能够完整容纳时直接保留，新增发言追加在原话之后；超过预算时才按相关性选取并保持时间顺序，不因“近期/旧记忆”分类改变旧发言位置。角色资料、案情变化会自然改变对应前缀；存档恢复从权威状态确定性重建，不持久化另一份提示词或模型回复缓存。压缩历史、新增线索等仍可能缩短可复用前缀，不能为缓存命中保留越权资料。

[DeepSeek 上下文缓存](https://api-docs.deepseek.com/zh-cn/guides/kv_cache/)由供应商自动处理相同请求前缀，应用不需要额外开关或预热调用。`logs/llm/*.jsonl` 的 `cache` 记录供应商实际返回的命中/未命中 token 数与比例；没有指标时为 `null`，不按零命中计算。`context.cache_prefix_sha256` 仅用于检查固定前缀是否改变，不是供应商缓存键，也不能证明命中。按模型、游戏、角色、生成/审查/投票阶段查看 token 加权统计：

```bash
cd backend
python -m app.core.prompt_cache --game-id <游戏ID>
# 或只统计指定日志
python -m app.core.prompt_cache logs/llm/2026-10-02.jsonl
```

缓存命中取决于供应商的缓存状态；固定前缀增加复用机会，不保证每次命中。统计同时列出 `reported_calls` 与 `unknown_calls`，只用有完整指标的请求计算命中率。

角色通过 `submit_statement.segments` 按顺序提交每句话及来源，后端拼成唯一正文，避免正文与陈述摘要不一致。后端检查来源可见性、证言类别、明确时间及更正归属；混合引用文书与本人知识的亲历陈述，会先移除文书引用，再仅按剩余事实审查，绝不把文书升级为事实。独立审查覆盖后端拆出的所有分句，引号中的证据原文保持完整；每个事实分句必须对应已登记的陈述及真实支持原文。审查纠正引用时，只能使用角色已可见的来源，并把实际核对后的引用保存到事件中。DeepSeek 官方端点默认由 V4 Flash 扮演、V4 Pro 审查（可用 `ROLEPLAY_REVIEW_MODEL` 指定）；其他端点默认复用其扮演模型。审查请求也保持每角色稳定前缀和独立缓存统计。

`cover_story` 单独保存作者明确允许的掩饰，不与 `self_knowledge` 真实经历混在一起。旧档混合真假行动的段落降为待核实笔录。公开自我介绍直接使用角色公开身份，不再让模型扩写履历。讨论失败后将明确标记为无效的草稿与具体错误提供给修复模型，最多重试一次；草稿不会成为事件或长期记忆。仍失败则优先返回与问题相关的本人剧本原句，凶手只使用允许的对外说辞，不因失败自白；没有相关原句时才引用出示证据并说明未知，避免反复粘贴整条线索。投票理由也接受审查，失败弃权。检查通过后才推送 SSE 和记录事件。独立审查会增加调用与延迟，仍不能保证消除所有自然语言幻觉。

会话快照版本为 4（兼容旧版，保留终局意见快照与活动时间，并冻结完整剧本正文），以 `discussion_events` 为权威记录，`discussion_history` 是兼容旧客户端的公共文本投影。旧快照的公共发言按原顺序迁移，缺失阶段/轮次保留为空；旧 AI 缓存中未出现在公共记录的条目作为仅该角色可见的旧证言保存。恢复时不再维护第二份 AI 对话记忆。

新剧本在制作阶段完成结构、各可扮演角色的三轮证据可达性和语义一致性检查，再将 `production.status=ready` 与正文一起原子保存。成品开局、旧剧本读取、继续存档及基础复盘仅做本地操作，不调用在线审稿或画像生成；旧存档没有制作元数据仍兼容读取，不补造新版审稿证明。明确修订剧本时应制作独立新版本并重新审稿，不修改正在游玩的故事。

《子夜当铺血案》已修订伤情、时间线与声响机关，把定案所需的检验、通道和归属证据放进可调查线索，增加作者侧证据映射。已经记录的旧对话不会被改写，检查新版内容请新开一局。

开发启动器使用每次启动的随机标识、后端 PID 和 HTTP 就绪响应共同确认端口；旧 `.port.json` 不会启动错误代理，就绪超时会停止进程。可用 `node --test scripts/backend-ready.test.js` 验证。

手机界面采用专用首页、固定底部搜证操作栏、聊天对象/证据底部选择面板与紧凑投票列表。玩家发言的询问对象和出示证据显示为中文标签，内部编号仍保存在原始事件中用于权限与恢复；不会自动翻译或改写已有玩家发言。NPC 正文中的纯英文、内部编号和未解码标记在发布前进入修复流程。

### 原创剧本库

首页默认提供三个预制原创剧本（3、5、7 人），无需重新生成或审稿。自行生成支持自动人数或指定 3—8 个角色，并提示质量受模型影响。可导入 JSON 剧本包并升级个人剧本；新游戏使用新版，已开始的游戏冻结原版。详见 [剧本包格式与扩展说明](docs/story-library.md)。

首批精选本已内置 3 张场景封面和 15 张角色头像，Android 直接加载 APK 资源，图片总计约 1.12 MiB。新增三个文字本使用现有案卷与姓名头像，不触发开局生图。电脑版生图服务与安卓后续独立 DashScope 接入范围见 [配图记录](docs/story-artwork.md)；安卓版在线生图尚未接通。
