# 🎭 剧本杀 - Murder Mystery Game

![Art Deco Noir Style](https://img.shields.io/badge/Style-Art%20Deco%20Noir-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)

一个基于 CAMEL-AI 框架的 AI 剧本杀游戏。玩家可以与 AI 角色进行实时对话、调查线索、讨论案情、指认凶手，体验完整的剧本杀游戏流程。

## ✨ 功能特点

### 🎯 核心功能
- **AI 角色扮演** - 使用 CAMEL-AI 框架实现智能 NPC，每个角色都有独特的对话风格和性格
- **AI 剧本生成** - 输入任意主题，AI 自动生成完整剧本（人物、线索、真相）
- **完整游戏流程** - 自我介绍 → 搜证 → 讨论 → 投票 → 真相揭晓

### 🔍 搜证系统
- **三类线索** - 物证（Physical）、证词（Testimony）、文书（Document）
- **线索分配** - 初始线索随机分配，可返回搜证获取更多
- **线索详情** - 点击查看完整线索内容

### 💬 讨论系统
- **实时对话** - 与 AI 角色进行自然语言交流
- **多轮讨论** - 支持多个讨论回合
- **返回搜证** - 讨论中途可返回搜证获取新线索

### ⚖️ 指认与投票
- **指认凶手** - 随时可以指认凶手（每局只有一次机会）
- **投票表决** - 所有玩家投票选出凶手
- **平票处理** - 平票时进入再讨论环节

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
└───────┼──────────────┼──────────────┼──────────────┼──────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │    REST API (8000)  │
                    │   - /games          │
                    │   - /stories        │
                    │   - /accuse         │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Game Manager  │  │Story Service  │  │  AI Agents   │
│   (游戏逻辑)   │  │  (剧本生成)   │  │  (对话生成)   │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   游戏状态     │  │   剧本存档     │  │  LLM API      │
│  (Phase, etc) │  │  (Characters, │  │ (DeepSeek/    │
│               │  │   Clues, etc)  │  │  MiniMax)     │
└───────────────┘  └───────────────┘  └───────────────┘
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
              │                             │
              ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│    4a. 讨论阶段 💬       │   │    4b. 指认凶手 ⚡       │
│ • 与AI角色对话            │   │  (每局仅一次机会!)        │
│ • 分享线索信息            │   │  • 选择嫌疑人             │
│ • 进入投票                │   │  • 确认指认               │
└─────────────┬───────────┘   │  • 正确→好人胜利         │
              │                 │  • 错误→凶手逃脱         │
              │                 └─────────────────────────┘
              │                             │
              └──────────────┬────────────────┘
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
git clone <your-repo-url>
cd MurderMystery
```

### 2. 配置 API 密钥

本项目需要 LLM API 密钥来驱动 AI 角色。

推荐使用 **DeepSeek** 或 **MiniMax M2-her**（专为大模型角色扮演优化的模型）。

```bash
# 进入后端目录
cd backend

# 复制环境变量模板
cp .env.simple .env

# 编辑 .env 文件，填入你的密钥
# Linux/Mac:
nano .env
# Windows:
notepad .env
```

`.env` 文件内容示例：

```env
# DeepSeek API (通用推理)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-reasoner

# MiniMax API (推荐用于角色扮演)
MINIMAX_API_KEY=sk-api-xxxxxxxxxxxxxxxx
MINIMAX_BASE_URL=https://api.minimax.com/v1
MINIMAX_MODEL=M2-her
```

> 💡 **获取 API 密钥**:
> - DeepSeek: https://platform.deepseek.com/
> - MiniMax: https://www.minimax.io/

### 3. 安装依赖

**后端**
```bash
cd backend
pip install -r requirements.txt
```

**前端**
```bash
cd frontend
npm install
```

### 4. 启动服务

**方式一：一键启动 (Linux/Mac)**
```bash
./start.sh
```

**方式二：手动启动**

终端 1 - 后端服务:
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

终端 2 - 前端服务:
```bash
cd frontend
npm run dev
```

### 5. 开始游戏

打开浏览器访问: **http://localhost:5173**

1. 输入剧本主题（如"公寓谋杀案"、"豪门恩怨"）
2. 点击创建游戏
3. 系统会分配你一个角色
4. 按照游戏流程进行！

## 📚 API 文档

启动服务后访问: **http://localhost:8000/docs**

### 主要接口

| 方法 | 端点 | 描述 |
|:---:|------|------|
| `GET` | `/stories` | 获取剧本列表 |
| `POST` | `/games` | 创建新游戏 |
| `GET` | `/games/{id}` | 获取游戏状态 |
| `GET` | `/games/{id}/clues` | 获取线索列表 |
| `POST` | `/games/{id}/introduce` | 提交自我介绍 |
| `POST` | `/games/{id}/speak` | 发送发言 |
| `POST` | `/games/{id}/accuse` | 指认凶手 |
| `POST` | `/games/{id}/vote` | 投票 |
| `GET` | `/games/{id}/reveal` | 获取真相揭示 |

## 🛠️ 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| [FastAPI](https://fastapi.tiangolo.com/) | 高性能 Web 框架 |
| [CAMEL-AI](https://www.camel-ai.org/) | AI Agent 框架 |
| [Pydantic](https://docs.pydantic.dev/) | 数据验证 |
| [Uvicorn](https://www.uvicorn.org/) | ASGI 服务器 |

### 前端
| 技术 | 用途 |
|------|------|
| [React 19](https://react.dev/) | UI 框架 |
| [TypeScript](https://www.typescriptlang.org/) | 类型安全 |
| [Vite](https://vitejs.dev/) | 构建工具 |
| [React Router](https://reactrouter.com/) | 路由管理 |
| [Lucide React](https://lucide.dev/) | 图标库 |

## 🔧 开发指南

### 项目结构

```
MurderMystery/
├── backend/
│   ├── app/
│   │   ├── agents/          # AI 角色代理
│   │   │   ├── base.py         # 基础代理类
│   │   │   └── m2_character.py # 多角色管理
│   │   ├── api/              # API 路由
│   │   ├── core/            # 核心逻辑
│   │   │   └── phases.py       # 游戏阶段定义
│   │   ├── domain/          # 领域模型
│   │   │   ├── models.py       # 数据模型
│   │   │   └── game_manager.py # 游戏管理器
│   │   ├── services/        # 业务服务
│   │   ├── main.py          # FastAPI 入口
│   │   └── cli.py           # CLI 工具
│   ├── stories/              # 剧本存档
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/             # API 客户端
│   │   ├── components/      # React 组件
│   │   ├── context/         # React Context
│   │   ├── pages/           # 页面组件
│   │   └── styles/          # 全局样式
│   ├── package.json
│   └── vite.config.ts
└── start.sh                 # 启动脚本
```

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 前端类型检查
cd frontend
npx tsc --noEmit
```

## ❓ 常见问题

**Q: 申请 API 密钥需要付费吗？**

A: DeepSeek 和 MiniMax 都提供免费额度。推荐使用 MiniMax M2-her 模型，它是专门的角色扮演优化模型，角色对话效果更好。

**Q: 游戏过程中 AI 响应很慢怎么办？**

A: 可以尝试使用更快的模型，或检查网络连接。首次生成剧本可能需要 1-2 分钟。

**Q: 可以自定义剧本吗？**

A: 可以！剧本以 JSON 格式存储在 `backend/stories/` 目录。你可以导入自定义剧本。

**Q: 支持多人联机吗？**

A: 当前版本每个游戏只有一个人类玩家，其他角色由 AI 控制。多人版本正在开发中。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
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
