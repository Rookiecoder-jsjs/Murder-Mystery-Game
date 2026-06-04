# 🎭 剧本杀 - Murder Mystery Game

![Art Deco Noir Style](https://img.shields.io/badge/Style-Art%20Deco%20Noir-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge)
![Tests](https://img.shields.io/badge/Tests-64%20passed-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)

一个基于 CAMEL-AI 框架的 AI 剧本杀游戏。玩家可以与 AI 角色进行实时对话、调查线索、讨论案情、指认凶手，体验完整的剧本杀游戏流程。

## ✨ 功能特点

### 🎯 核心功能
- **AI 角色扮演** - 使用 CAMEL-AI 框架实现智能 NPC，每个角色都有独特的对话风格和性格
- **AI 剧本生成** - 输入任意主题，AI 自动生成完整剧本（人物、线索、真相）
- **完整游戏流程** - 自我介绍 → 搜证 → 讨论 → 投票 → 真相揭晓
- **⚡ 实时流式对话** - SSE 流式输出，AI 角色边生成边显示

### 🔍 搜证系统
- **三类线索** - 物证（Physical）、证词（Testimony）、文书（Document）
- **线索分配** - 初始线索随机分配，可返回搜证获取更多
- **线索详情** - 点击查看完整线索内容

### 💬 讨论系统
- **实时对话** - 与 AI 角色进行自然语言交流
- **⚡ 并发响应** - 多个 AI 角色并行生成，玩家无需串行等待
- **SSE 流式输出** - 每个角色的回复独立推送，边生成边渲染
- **多轮讨论** - 支持多个讨论回合
- **返回搜证** - 讨论中途可返回搜证获取新线索

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
│  │  clue_system.py     线索分配/解锁                      │   │
│  │  models.py          数据模型（dataclass）              │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │   app/agents/  — AI 角色                              │   │
│  │  m2_character.py     M2-her 角色扮演                   │   │
│  │  generator_agent.py  DeepSeek 故事生成                 │   │
│  └──────────────────────┬───────────────────────────────┘   │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │   LLM API              │
                │   DeepSeek + M2-her    │
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

本项目需要 LLM API 密钥来驱动 AI 角色。

推荐使用 **DeepSeek**（故事生成） + **MiniMax M2-her**（角色扮演）。

```bash
# 进入后端目录
cd backend

# 复制环境变量模板
cp .env.simple .env

# 编辑 .env，填入你的密钥
# Linux/Mac:
nano .env
# Windows:
notepad .env
```

`.env` 文件关键配置（完整列表见 `.env.simple`）：

```env
# 故事生成
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-reasoner

# 角色扮演
MINIMAX_API_KEY=sk-api-xxxxxxxxxxxxxxxx
MINIMAX_BASE_URL=https://api.minimax.com/v1
MINIMAX_MODEL=M2-her
```

> 💡 **获取 API 密钥**:
> - DeepSeek: https://platform.deepseek.com/
> - MiniMax: https://www.minimax.io/

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
| `DEEPSEEK_API_KEY` | — | 故事生成必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek 端点 |
| `DEEPSEEK_MODEL` | `deepseek-reasoner` | 故事生成模型 |
| `MINIMAX_API_KEY` | — | 角色扮演必需 |
| `MINIMAX_BASE_URL` | `https://api.minimax.com/v1` | MiniMax 端点 |
| `MINIMAX_MODEL` | `M2-her` | 角色扮演模型 |
| `M2_TEMPERATURE` | `1.0` | 角色生成温度 |
| `M2_TOP_P` | `0.95` | 角色生成 top_p |
| `M2_MAX_TOKENS` | `2048` | 角色生成最大 token |
| `CORS_ALLOWED_ORIGINS` | localhost dev | 逗号分隔；不设则只允许本地 |
| `LOG_LEVEL` | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `SESSIONS_DIR` | — | 不设则内存存储；设了启用 JSON 持久化 |

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
| `POST` | `/games/{id}/introduce` | 提交自我介绍 |
| `POST` | `/games/{id}/speak` | 发送发言（批式，所有 AI 回复一次返回） |
| `POST` | `/games/{id}/speak/stream` | **发送发言（SSE 流式，AI 完成一个推送一个）** |
| `POST` | `/games/{id}/accuse` | 指认凶手 |
| `POST` | `/games/{id}/vote` | 投票 |
| `POST` | `/games/{id}/start-voting` | 进入投票阶段 |
| `POST` | `/games/{id}/return-to-investigation` | 返回搜证 |
| `GET` | `/games/{id}/reveal` | 获取真相揭示 |
| `GET` | `/games/{id}/discussion-history` | 讨论历史 |

### SSE 流式响应示例

```bash
curl -N -X POST http://localhost:8000/games/{id}/speak/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "我觉得 Alice 很可疑"}'
```

事件流（每行 SSE event）：

```
event: message
data: {"speaker": "玩家", "message": "我觉得 Alice 很可疑"}

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
| [CAMEL-AI](https://www.camel-ai.org/) | AI Agent 框架 |
| [OpenAI SDK](https://github.com/openai/openai-python) | M2-her / DeepSeek 客户端 |
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
│   │   │   ├── m2_character.py    M2-her 角色扮演
│   │   │   └── generator_agent.py DeepSeek 剧本生成
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
│   │   │   └── prompts.py        Prompt 模板
│   │   ├── domain/           纯领域逻辑
│   │   │   ├── game_manager.py   阶段/投票/指认
│   │   │   ├── clue_system.py    线索分配
│   │   │   └── models.py         数据模型
│   │   ├── services/         业务服务
│   │   │   ├── session_service.py  GameSession + SessionManager
│   │   │   └── story_service.py    剧本生成与存档
│   │   ├── main.py           FastAPI 入口（75 行）
│   │   └── cli.py            CLI 工具
│   ├── stories/              剧本存档
│   ├── tests/                pytest 单元测试
│   │   ├── conftest.py
│   │   ├── test_game_manager.py   46 个测试
│   │   └── test_clue_system.py    18 个测试
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
# 后端：64 个单元测试（< 1 秒）
npm run test:backend
# 或
cd backend && python -m pytest

# 前端类型检查
cd frontend && npx tsc --noEmit

# 单个文件
cd backend && python -m pytest tests/test_game_manager.py -v
```

测试覆盖：阶段转换、投票（多数/平局）、指认（对/错/限额）、线索分配与解锁、淘汰、讨论历史、游戏摘要等。

## ❓ 常见问题

**Q: 在 Windows 上 `npm run dev` 启动报 `'vite' 不是内部或外部命令`？**

A: 已修复。当前脚本用 `node node_modules/vite/bin/vite.js` 直接调用 Vite，绕开了 cmd.exe 的 PATH 问题。如仍报，请确认 `frontend/node_modules` 已安装（`npm run install:all`）。

**Q: 申请 API 密钥需要付费吗？**

A: DeepSeek 和 MiniMax 都提供免费额度。推荐使用 MiniMax M2-her 模型，它是专门的角色扮演优化模型，角色对话效果更好。

**Q: 游戏过程中 AI 响应很慢怎么办？**

A: 1) 首次生成剧本需要 1-2 分钟（DeepSeek Reasoner 思考时间）；2) 讨论阶段已用 thread pool 并发触发所有 AI 角色；3) SSE 流式让前端在第一个角色完成时就开始渲染。如仍慢，可调低 `M2_MAX_TOKENS`。

**Q: 重启后游戏状态会丢吗？**

A: 默认内存存储会丢。设 `SESSIONS_DIR=backend/sessions` 即可启用 JSON 持久化，启动时自动恢复。

**Q: 可以自定义剧本吗？**

A: 可以！剧本以 JSON 格式存储在 `backend/stories/` 目录。通过 `/games/load` 端点加载已有 story_id。

**Q: 支持多人联机吗？**

A: 当前版本每个游戏只有一个人类玩家，其他角色由 AI 控制。多人版本正在开发中。

**Q: SSE 流式和普通 /speak 端点的区别？**

A: `/speak` 等所有 AI 完成后一次性返回；`/speak/stream` 用 Server-Sent Events 每完成一个 AI 角色就推一条 `message` 事件。已实现前端自动回退：流式失败时降级用批式。

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

- [CAMEL-AI](https://www.camel-ai.org/) - 提供了强大的 AI Agent 框架
- [DeepSeek](https://platform.deepseek.com/) - 提供高性能 LLM API
- [MiniMax](https://www.minimax.io/) - 提供 M2-her 角色扮演专用模型
- 所有开源贡献者

---

⭐ 如果这个项目对你有帮助，请 star 支持一下！
