# AGENT.md

本文件是本仓库的代码库规则与开发约定。修改代码前先阅读本文件，并以现有实现、测试和类型定义为准；不要为了追求“统一”而大范围改写既有结构。

## 项目概览

这是一个基于 OpenAI 兼容大模型 API 的 AI 剧本杀游戏，包含三个协同部分：

- `backend/`：Python 3.11+、FastAPI、pytest。负责剧本生成、AI 角色扮演、游戏状态机、线索、投票和会话持久化。
- `frontend/`：React 19 + TypeScript + Vite 的 Web 客户端。
- `miniprogram/`：Taro 4 + React 18 + TypeScript 的微信小程序客户端，复用同一套后端 API。

游戏阶段及其字符串值必须保持一致：

`introduction` → `investigation` → `discussion` → `voting` → `reveal`

## 开发前检查

先确认工作区状态，避免覆盖他人改动：

```bash
git status --short --branch
```

仓库已初始化 CodeGraph。需要理解或定位代码时，优先使用：

```bash
codegraph explore "你的问题或目标符号"
codegraph node SymbolName
codegraph status
```

代码变更后如需更新索引，使用 `codegraph sync`；不要手工编辑 `.codegraph/` 内的索引文件。

## 目录职责

### 后端

- `backend/app/main.py`：FastAPI 应用入口、生命周期、CORS、静态资源和总路由装配；保持薄，不放业务逻辑。
- `backend/app/api/endpoints/`：HTTP 路由处理器，只负责参数校验、依赖注入、调用服务和组装响应。
- `backend/app/api/schemas.py`：HTTP 请求/响应数据结构。API 形状变化时同步更新客户端类型与测试。
- `backend/app/services/session_service.py`：单局运行时、会话管理、LLM 调用编排和会话持久化。
- `backend/app/services/story_service.py`：剧本生成、解析、存档和人物肖像调度。
- `backend/app/services/image_service.py`：肖像生成与本地资源管理。
- `backend/app/domain/`：游戏领域模型和状态机；应尽量保持与 FastAPI、文件系统和具体 LLM SDK 解耦。
- `backend/app/agents/`：AI 角色行为、角色提示词和对话记忆。
- `backend/app/core/`：配置、阶段枚举、日志、端口探测和 LLM 追踪等基础设施。
- `backend/tests/`：后端单元测试和 API 测试；测试文件按被测模块命名。
- `backend/stories/`：剧本 JSON 存档和测试/开发所需内容。修改存档结构时必须考虑已有存档的兼容读取。

### 客户端

- `frontend/src/api/`：Web API 客户端、SSE 解析和 TypeScript 数据类型。组件不得各自重复实现 API 请求。
- `frontend/src/context/`：Web 游戏全局状态和动作。
- `frontend/src/pages/`：页面级路由入口。
- `frontend/src/components/`：按游戏阶段和通用能力拆分的 React 组件；样式与组件就近维护。
- `miniprogram/src/services/`：小程序 HTTP/API 封装。
- `miniprogram/src/store/`：小程序游戏状态。
- `miniprogram/src/features/game/`、`miniprogram/src/pages/`、`miniprogram/src/components/`：小程序业务功能、页面和展示组件。
- `scripts/`：跨平台开发启动器。动态端口由后端写入 `backend/.port.json`，前端开发服务器读取该文件进行代理配置。

## 架构与实现规则

1. 路由层必须保持薄。新增业务流程应优先放入 `services/` 或 `domain/`，不要在 `endpoints/games.py` 中堆积状态变更和 LLM 逻辑。
2. `domain/` 中的核心游戏规则应可脱离 HTTP 运行。不要把 FastAPI `Request`、响应模型、环境变量读取或具体客户端细节引入领域模型。
3. 所有游戏状态变更必须经过 `GameManager` / `GameSession` 的现有方法，不能从路由或 UI 直接修改内部状态字典。
4. LLM 调用必须遵守现有异步边界，不能在 FastAPI 事件循环中直接执行阻塞调用；沿用已有的线程池/异步封装、超时和错误转换方式。
5. 修改 API 时同时检查四处：后端路由/Schema、Web `frontend/src/api/`、小程序 `miniprogram/src/services/` 与类型、对应测试。
6. 流式对话接口使用 SSE。修改事件名、数据结构、终止事件或超时行为时，必须同步更新 Web 端解析器和小程序端兼容逻辑，并覆盖失败/断流场景。
7. 会话持久化是可插拔的：默认内存存储；设置 `SESSIONS_DIR` 后使用 JSON 文件存储。新增状态字段时必须提供缺省值或迁移兼容逻辑。
8. 游戏阶段、投票、指认、平票重投和揭晓的行为属于核心规则。改变阶段转换或胜负判定时，必须先补充或修改 `backend/tests/test_game_manager.py` 及相关服务/API 测试。
9. 面向玩家的文案以中文为主，保持现有游戏术语、阶段名称和错误提示风格；不要无理由改动既有文案或 API 字段的中英文命名。

## 代码风格

### Python

- 使用 `snake_case` 的文件、函数和变量名，类使用 `PascalCase`。
- 新增公共函数、服务方法和复杂状态转换应添加类型注解与简短 docstring。
- 优先复用现有配置、日志和异常处理设施，不在业务代码中散落 `print`、硬编码密钥或环境变量解析。
- 路径使用 `pathlib`；JSON 使用 UTF-8，并保留中文内容。
- 异步接口不得引入新的同步阻塞调用；外部 API、文件操作和耗时任务要明确其执行边界。

### TypeScript / React

- 遵守现有严格 TypeScript 配置：避免 `any`、未使用变量和未处理的 `undefined`。
- 组件、页面和类型使用 `PascalCase`；函数、变量和 API 方法使用 `camelCase`；文件名沿用所在目录的现有风格。
- API 类型是契约来源之一。不要在组件内重复声明后端响应结构。
- Web 端通过 `frontend/src/api/client.ts` 请求后端；小程序端通过 `miniprogram/src/services/game-api.ts` 和 `http.ts` 请求后端。
- 样式修改优先使用现有 CSS/SCSS 变量、设计 token 和组件结构，保持 Art Deco Noir / 案卷风格，不引入无必要的 UI 框架。
- 不要为了修复单个页面而破坏 Web 与小程序之间共享的后端语义。

## 常用命令

首次安装：

```bash
npm run install:all
pip install -r backend/requirements.txt
```

本地开发：

```bash
npm run dev                 # 同时启动后端和 Web 前端，推荐
npm run dev:backend         # 仅后端
npm run dev:frontend        # 仅 Web 前端
```

后端验证：

```bash
npm run test:backend
cd backend && python -m pytest
cd backend && python -m pytest tests/test_game_manager.py -v
```

Web 验证：

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

小程序验证：

```bash
cd miniprogram && pnpm install --frozen-lockfile
cd miniprogram && pnpm run typecheck
cd miniprogram && pnpm run build:weapp
```

没有专门的前端单元测试脚本时，至少运行受影响端的 lint、typecheck 或 build，并在最终说明实际运行过的命令。

## 配置、数据与安全

- 密钥只放在 `backend/.env`，不要提交 `.env`、API key、访问令牌或真实用户数据。
- 启动时后端会校验必需的 LLM 配置；缺少密钥时的快速失败属于预期行为，不要通过硬编码默认密钥规避。
- `backend/assets/portraits/`、`backend/sessions/`、`backend/.port.json` 和各端构建产物属于运行时/生成文件，除非任务明确要求，不要提交。
- 处理剧本 JSON 时保留合法 JSON、UTF-8 编码和现有字段语义；不要把日志、推理过程或密钥写入存档。
- 不要为了“清理”而删除已有剧本、会话、肖像或用户改动；删除前必须确认目标和范围。

## Git 与交付规则

- 默认在独立分支开发，不直接改写已推送的共享历史，不对 `master` 强制推送。
- 提交信息沿用仓库已有的 Conventional Commits 风格，例如 `feat: ...`、`fix: ...`、`perf: ...`、`chore: ...`。
- 每次修改尽量小而聚焦；不要把格式化、依赖升级和无关重构混入功能修复。
- 提交或交付前检查 `git diff`、`git status`，确认没有密钥、构建产物、临时文件或意外生成数据。
- API、游戏规则、持久化格式或启动命令发生变化时，同步更新 README、类型、测试和本文件中受影响的说明。
- 最终报告应简要说明：改了什么、运行了哪些验证命令、是否还有已知限制或未验证部分。
