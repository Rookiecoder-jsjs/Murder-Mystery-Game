# 🎭 剧本杀 - Murder Mystery Game

![Art Deco Noir Style](https://img.shields.io/badge/Style-Art%20Deco%20Noir-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge)
![Tests](https://img.shields.io/badge/Tests-65%20passed-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)

一个基于 OpenAI 兼容大模型 API 的 AI 剧本杀游戏。玩家可以与 AI 角色进行实时对话、调查线索、讨论案情、指认凶手，体验完整的剧本杀游戏流程。

## ✨ 功能特点

### 🎯 核心功能
- **AI 角色扮演** - 每个角色都有独特的对话风格、隐藏秘密与凶手伪装策略
- **AI 剧本生成** - 输入任意主题，AI 自动生成完整剧本（人物、线索、真相）
- **AI 人物肖像** - 基于角色公开身份与外貌，自动生成并保存民国档案肖像
- **完整游戏流程** - 自我介绍 → 搜证 → 讨论 → 投票 → 真相揭晓
- **⚡ 实时流式对话** - SSE 流式输出，AI 角色边生成边显示
- **上下文感知** - AI 角色能看到自己的线索、公开线索、其他角色身份与完整讨论历史

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
- **投票表决** - 所有玩家投票选出凶手
- **平票处理** - 平票时进入再讨论环节

### 💾 会话持久化
- **进程重启不丢失** - 会话状态自动落盘到 JSON
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
│  │  game_manager.py    阶段/投票/指认                     │   │
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
│              所有玩家投票选择凶手                           │
│    • 多数票→揭示真相                                      │
│    • 平票→再讨论→重新投票                                  │
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

## 🚀 快速开始

### 环境要求

- **Python**: 3.11+
- **Node.js**: 18+
- **包管理器**: pip, npm

### 1. 克隆项目

```bash
git clone https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game.git
cd Murder-Mystery-Game
```

### 2. 配置 API 密钥

本项目需要 LLM API 密钥来驱动 AI 角色；若启用自动人物肖像，还需要 DashScope API 密钥。

使用 **DeepSeek V4 Pro**（故事生成，禁用思考模式以降低延迟）+ **DeepSeek V4 Flash**（角色扮演，低延迟），单一供应商、一个 API key 即可。

密钥存放在 **`backend/.env`**（相对路径以 `backend/` 为基准解析，与启动目录无关）；该文件已被根目录 `.gitignore` 忽略，**绝不会被提交**。

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
> 🖼️ **肖像存储**：新剧本会为每个角色并发生成一张 2:3 肖像，成功图片立即下载到 `backend/assets/portraits/<剧本ID>/`，并将访问路径写入该剧本 JSON。DashScope 密钥缺失或单张失败时，剧本仍可正常创建，并回退为首字母头像。

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

1. 输入剧本主题（如"公寓谋杀案"、"豪门恩怨"）
2. 点击创建游戏
3. 系统会分配你一个角色
4. 按照游戏流程进行！

### 速推模式

新建案件时可以选择“速推模式”或“经典模式”：

- 速推模式固定 3 轮调查；每轮从两个调查方向中选择一个，获得线索并触发案件突破事件，适合 10–15 分钟完成一局。
- 速推模式每轮只能执行一次调查行动；完成调查后才能进入讨论，避免通过重复搜证跳过推理决策。
- 经典模式保留自由调查和原有随机搜证流程，适合更完整的沉浸式体验。
- 速推模式完成全部调查轮次后才能进入投票；未完成时可以从讨论返回下一轮搜证。

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
| `DEEPSEEK_MODEL` | `deepseek-v4-pro` | 故事生成模型（思考模式关闭） |
| `ROLEPLAY_API_KEY` | 复用 `DEEPSEEK_API_KEY` | 角色扮演密钥（可选，通常不设） |
| `ROLEPLAY_BASE_URL` | 复用 `DEEPSEEK_BASE_URL` | 角色扮演端点（可选） |
| `ROLEPLAY_MODEL` | `deepseek-v4-flash` | 角色扮演模型（思考模式关闭） |
| `ROLEPLAY_TEMPERATURE` | `1.0` | 角色生成温度（思考模式下无效） |
| `ROLEPLAY_TOP_P` | `0.95` | 角色生成 top_p（思考模式下无效） |
| `ROLEPLAY_MAX_TOKENS` | `2048` | 角色生成最大 token |
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
| `POST` | `/games/{id}/vote` | 投票 |
| `POST` | `/games/{id}/start-voting` | 进入投票阶段 |
| `POST` | `/games/{id}/return-to-investigation` | 返回搜证 |
| `POST` | `/games/{id}/return-to-discussion` | 投票未达成结果时直接返回讨论，不开启新一轮搜证 |
| `GET` | `/games/{id}/reveal` | 获取真相揭示 |
| `GET` | `/games/{id}/discussion-history` | 讨论历史 |

### SSE 流式响应示例

```bash
curl -N -X POST http://localhost:8000/games/{id}/speak/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "我觉得 Alice 很可疑"}'
```

事件流（每行 SSE event；玩家自己的消息由前端乐观回显，服务端只推送 AI 回复）：

```
event: message
data: {"speaker": "Bob", "message": "..."}

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
│   │   │   └── roleplay_character.py  V4-Flash 角色扮演（含上下文组装）
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

测试覆盖：阶段转换、投票（多数/平局/重投清票）、指认（对/错/限额/自我/淘汰目标）、线索分配与解锁链、淘汰、讨论历史、会话快照往返、JSON 持久化恢复等。

## ❓ 常见问题

**Q: 在 Windows 上 `npm run dev` 启动报 `'vite' 不是内部或外部命令`？**

A: 已修复。当前脚本用 `node node_modules/vite/bin/vite.js` 直接调用 Vite，绕开了 cmd.exe 的 PATH 问题。如仍报，请确认 `frontend/node_modules` 已安装（`npm run install:all`）。

**Q: 申请 API 密钥需要付费吗？**

A: DeepSeek 提供免费注册和低成本按量计费，还有错峰半价。故事生成用 V4 Pro（质量优先），角色对话用 V4 Flash（速度优先、更便宜）。

**Q: 游戏过程中 AI 响应很慢怎么办？**

A: 1) 首次生成剧本需要一些时间；2) 讨论阶段已用 thread pool 并发触发所有 AI 角色；3) SSE 流式让前端在第一个角色完成时就开始渲染。如仍慢，可调低 `ROLEPLAY_MAX_TOKENS`。

**Q: 重启后游戏状态会丢吗？**

A: 默认内存存储会丢。设 `SESSIONS_DIR=backend/sessions` 即可启用 JSON 持久化，启动时自动恢复。

**Q: 可以自定义剧本吗？**

A: 可以！剧本以 JSON 格式存储在 `backend/stories/` 目录。通过 `/games/load` 端点加载已有 story_id。

**Q: 支持多人联机吗？**

A: 当前版本每个游戏只有一个人类玩家，其他角色由 AI 控制。多人版本正在开发中。

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

本项目基于 Apache License 2.0 许可证开源。

Copyright 2023-2026 CAMEL-AI.org. All Rights Reserved.

## 🙏 致谢

- [DeepSeek](https://platform.deepseek.com/) - 提供 V4 Pro / V4 Flash LLM API
- 所有开源贡献者

---

⭐ 如果这个项目对你有帮助，请 star 支持一下！
