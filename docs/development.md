# 开发指南

[返回项目首页](../README.md)

安装安卓 APK 的玩家无需准备本页环境。本文用于运行 Web 服务、修改项目与构建安卓版本。

## 环境与首次启动

Web 开发需要 Python 3.11+、Node.js 22.12+、npm 和 OpenAI 兼容模型 API key。安卓构建还需要 JDK 21、Android SDK 36、Python 3.11 构建解释器。

从项目根目录创建虚拟环境，安装后端与 Web 依赖：

```bash
python -m venv .venv
```

Linux / macOS 激活：

```bash
source .venv/bin/activate
```

Windows PowerShell 激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD 激活：

```bat
.venv\Scripts\activate.bat
```

然后在已激活的终端执行：

```bash
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

首次配置时复制模板；已有 `backend/.env` 时直接编辑，避免覆盖原有配置。

```bash
cp backend/.env.simple backend/.env
```

Windows PowerShell 对应命令为 `Copy-Item backend/.env.simple backend/.env`。

填写 `DEEPSEEK_API_KEY`，核对服务地址与模型名称，再启动：

```bash
npm run dev
```

前端通常位于 `http://localhost:5173`。后端从 8000 起选择可用端口，启动器核对本次启动标识、PID 与 HTTP 就绪后再配置 Vite 代理。以终端打印的地址为准，后端 API 文档位于实际后端地址的 `/docs`。`Ctrl+C` 会停止本次前后端进程。

仅开发 Web 不需要 pnpm。若还要开发小程序，按 [小程序说明](../miniprogram/README.md) 安装 pnpm 依赖；根目录 `npm run install:all` 会同时安装小程序，不只是 Web。

## 模型与数据配置

完整变量和默认值以 [backend/.env.simple](../backend/.env.simple) 为准。模板中的 key 留空，真实密钥只填写到被 Git 忽略的 `backend/.env`。

| 配置 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 故事生成与审稿；也为角色请求提供默认密钥与地址 |
| `ROLEPLAY_MODEL` | 角色扮演模型 |
| `ROLEPLAY_API_KEY` / `ROLEPLAY_BASE_URL` | 可选：单独配置角色请求的密钥与地址 |
| `ROLEPLAY_REVIEW_MODEL` | 独立事实审查模型 |
| `ROLEPLAY_CONTEXT_TOKEN_BUDGET` | 输入上下文的估算预算，包含工具定义与重试余量 |
| `DASHSCOPE_API_KEY` 与 `DASHSCOPE_*` | 可选：电脑版新剧本的在线肖像生成 |
| `SESSIONS_DIR` | 设置为 `sessions` 可启用 Web JSON 存档；不设则为内存存储 |
| `CORS_ALLOWED_ORIGINS` / `LOG_LEVEL` | 服务访问来源与日志级别 |
| `LLM_TRACE_*` | 模型调用追踪；可能包含完整案情、提问与输出，排障时留意数据范围 |

默认模板把故事生成、扮演和审查分别配置为 DeepSeek 模型，也可使用支持所需请求格式的兼容服务。不同供应商的思考模式、工具调用和缓存行为可能不同；切换后应验证生成与角色回应。缺少必需密钥时，后端启动会快速失败。

相对数据路径以 `backend/` 为基准。在线生成肖像保存在 `backend/assets/portraits/`，新剧本存档在 `backend/stories/`；精选内容仅从 `backend/app/content/stories/manifest.json` 读取。成品开局、列表与继续旧局不触发审稿或生图。没有 DashScope key 或画像失败时使用姓名头像，详见 [配图说明](story-artwork.md)。

## 项目分工

| 目录 | 职责 |
| --- | --- |
| `backend/app/domain/` | 游戏规则、状态机与领域数据 |
| `backend/app/services/` | 制作剧本、会话、存档与模型调用编排 |
| `backend/app/agents/` | AI 角色行为与回应检查 |
| `backend/app/api/` | FastAPI 路由与请求响应结构 |
| `frontend/` | React 19 / TypeScript / Vite 8 界面，Web 与安卓共用 |
| `frontend/android/` | Capacitor / Chaquopy，原生模型请求、加密配置与内容下载 |
| `mobile_engine/` | 安卓本地 Python 引擎、任务与 SQLite 存档 |
| `miniprogram/` | Taro 微信小程序，连接 Web 后端 |
| `skills/update-mystery-stories/` | 项目专用故事创作与配图流程 |

Web 通过 FastAPI 和 SSE 调用游戏服务。安卓在 APK 内运行 Python 引擎，通过原生桥接直接请求模型服务，不启动 HTTP 后端，也不连接电脑。小程序使用同一套 Web 后端，尚未提供独立本地引擎。

修改前阅读 [AGENT.md](../AGENT.md)，理解代码时优先使用 `codegraph explore` / `codegraph node`，代码变化后按需运行 `codegraph sync`。

## 常用命令与验证

在根目录运行 `npm run dev:backend` 可仅启动后端，`npm run dev:frontend` 可仅启动 Web。单独启动前端时仍需可用后端及正确的端口文件。

后端规则与 API：

```bash
npm run test:backend
# 单个规则文件
cd backend
python -m pytest tests/test_game_manager.py -v
```

Web 测试、静态检查与构建（在 `frontend/` 执行）：

```bash
npm test
npm run lint
npm run build
```

小程序的验证与联调方法见 [小程序 README](../miniprogram/README.md)。验证范围按改动决定；真实模型游玩与离线回归测试分别记录。

## API 与流式对话

启动后以 FastAPI `/docs` 的实际请求、响应结构为准。主要入口为 `/stories`、`/games`、`/games/load` 和 `/games/{id}` 下的调查、发言、表决及揭晓动作。

- `game_id` 是本局会话 ID，`story_id` 是剧本 ID；客户端还需同步 `game_ended`、`winner`、`is_speaking` 与 `available_actions`。
- `/speak` 等所有角色完成后一次返回，`/speak/stream` 使用 SSE，先确认已保存的玩家问题，再推送检查通过的角色回复，最后发送 `done`。
- 发言可传 `target_id`、`presented_clue_ids`、UUID 格式的 `action_id`；出示线索会检查持有权并公开该证据。
- AI 回应期间拒绝并发动作。流断开后后台仍完成并保存回复，客户端应同步状态与历史，避免盲目重复提交。
- 最终 `/vote` 保存玩家选择并立即结案；`/ballot-advice` 是结案后按需获取的角色意见，不改变胜负。`/reveal` 只在终局开放。

```bash
curl -N -X POST 'http://localhost:8000/games/<game_id>/speak/stream' \
  -H 'Content-Type: application/json' \
  -d '{"message":"这条证据和你的说法有什么关系？"}'
```

上述地址仅为默认端口示例。事件正文及角色资料边界见 [AI 上下文说明](ai-context.md)。

## 构建安卓 APK

配置 `JAVA_HOME`、`ANDROID_HOME`，确保 Python 3.11 构建解释器可用；需要指定解释器时使用 `MMG_BUILD_PYTHON`。Chaquopy 将 Python 运行环境打包进 APK，玩家无需另行安装。

```bash
npm --prefix frontend ci
npm run android:apk
# APK：frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

构建会生成安卓页面、按白名单打包引擎与基础剧本，再执行 APK 审计。可单独复查：

```bash
python3 scripts/audit-android-apk.py frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

不得打包电脑 `.env`、真实 key、用户数据库、存档或日志。APK 作为 Release 附件交付；覆盖升级必须保留相同签名，并递增 `versionCode`。构建方法与真机限制见 [安卓实施记录](android-port-plan.md)，对应源码与许可交付见 [许可说明](licensing.md)。

## 扩展故事

使用 [本项目的 update-mystery-stories skill](../skills/update-mystery-stories/SKILL.md)，例如：

> 使用 $update-mystery-stories，主题是“雪山旅馆”，人数自动，生成剧本和全部配图，先完成本地检查。

skill 源码仅保存在仓库 `skills/`，由项目 `.agents/skills/` 的相对链接加载，不安装到全局。结构、证据可达性、真实模型审稿与实玩是不同验证，不能互相代替。

兼容故事与配图通过签名内容包更新，只有引擎或界面变化需要重新发布 APK。格式、签名和发布顺序分别见 [剧本包说明](story-library.md)、[内容更新链路](story-content-updates.md)。
