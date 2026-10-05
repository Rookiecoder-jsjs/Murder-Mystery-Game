# AGENT.md

本文件是本仓库的代码库规则与开发约定。修改代码前先阅读本文件，并以现有实现、测试和类型定义为准；不要为了追求“统一”而大范围改写既有结构。

## 项目概览

这是一个基于 OpenAI 兼容大模型 API 的 AI 剧本杀游戏，包含三个协同部分：

- `backend/`：Python 3.11+、FastAPI、pytest。负责剧本生成、AI 角色扮演、游戏状态机、线索、投票和会话持久化。
- `frontend/`：React 19 + TypeScript + Vite 的 Web 客户端。
- `miniprogram/`：Taro 4 + React 18 + TypeScript 的微信小程序客户端，复用同一套后端 API。

安卓独立运行开发版见 [实施记录与迁移方案](docs/android-port-plan.md)。`frontend/android/` 使用 Capacitor + Chaquopy；`mobile_engine/` 提供本地任务、SQLite 与模型适配。构建按源码白名单复用 `backend/app`，不得复制 `.env`、电脑存档或日志。APK 内运行游戏引擎，由原生层保存密钥并请求模型服务，不启动 HTTP 后端。当前采用竖屏手机布局；文档其余目标设计不代表全部完成。

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

`.codegraph/` 是本机索引与缓存，整个目录由根 `.gitignore` 忽略，不提交索引数据库、元数据或该目录中的 `.gitignore`。

新增或修订原创剧本及配图时，使用本项目的 [update-mystery-stories skill](skills/update-mystery-stories/SKILL.md)。源码只在仓库 `skills/` 中维护，项目 `.agents/skills/update-mystery-stories` 为相对链接；不要安装到全局技能目录。一般代码或 UI 修改不使用该 skill。

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
- `backend/app/content/stories/`：manifest 列出的原创内置数据包，来源和版本明确；不得扫描用户数据作为内置内容。包规范见 `docs/story-library.md`。
- `backend/app/services/story_content_service.py`：官方安装索引、版本合并与内容引用；与个人保存共用短时命名空间锁，不下载、不调用模型。
- `content/config.json` 与 `content/keys/`：Android 目录地址与受信公钥；只提交公钥。签名私钥必须位于仓库外，不进入 APK 或内容包。
- `scripts/package-story-content.py`：无模型的内容发布工具，默认 dry-run；签名时必须固定源码提交、递增内容/目录版本并复用已发布产物字节。
- `backend/app/content/images/`：原创内置配图，按剧本包 artwork 清单发布。Vite 构建复制到本地 Web/APK 资源，不携带生成密钥；升级图片使用新文件名并在 retained_files 保留历史 URL，见 `docs/story-artwork.md`。
- `backend/stories/`：剧本 JSON 存档和测试/开发所需内容。修改存档结构时必须考虑已有存档的兼容读取。

### 客户端

- `frontend/src/api/`：Web API 客户端、SSE 解析和 TypeScript 数据类型。组件不得各自重复实现 API 请求。
- `frontend/src/context/`：Web 游戏全局状态和动作。
- `frontend/src/pages/`：页面级路由入口。
- `frontend/src/pages/mobile/`：安卓首页／剧本库／我的及次级页面，共享本地目录与资料读取；详情操作固定在底部，官方列表保留当前进程内的搜索、筛选与位置。沿用 `libraryApi`、原生凭据与游戏状态动作，不能在 UI 中下载或校验内容包。实现见 `docs/android-lobby.md`。
- `frontend/src/components/`：按游戏阶段和通用能力拆分的 React 组件；样式与组件就近维护。
- Logo 原图为 `docs/brand/logo-casefile-source.png`，Web 派生资源在 `frontend/public/brand/`。替换图稿后运行 `python3 scripts/build-brand-assets.py`（需要 Pillow）更新网页、各密度 Android 图标和启动图；按中央安全区留白，不使用电脑或手机配置作为资源。说明见 `docs/logo-design.md`。
- `miniprogram/src/services/`：小程序 HTTP/API 封装。
- `miniprogram/src/store/`：小程序游戏状态。
- `miniprogram/src/features/game/`、`miniprogram/src/pages/`、`miniprogram/src/components/`：小程序业务功能、页面和展示组件。
- `scripts/`：跨平台开发启动器。动态端口由后端原子写入 `backend/.port.json`；联合启动器核对本次 launch_id、PID 与 HTTP 就绪后，通过 BACKEND_PORT 固定前端代理。单独启动前端仍读取端口文件。

## 架构与实现规则

1. 路由层必须保持薄。新增业务流程应优先放入 `services/` 或 `domain/`，不要在 `endpoints/games.py` 中堆积状态变更和 LLM 逻辑。
2. `domain/` 中的核心游戏规则应可脱离 HTTP 运行。不要把 FastAPI `Request`、响应模型、环境变量读取或具体客户端细节引入领域模型。
3. 所有游戏状态变更必须经过 `GameManager` / `GameSession` 的现有方法，不能从路由或 UI 直接修改内部状态字典。
4. LLM 调用必须遵守现有异步边界，不能在 FastAPI 事件循环中直接执行阻塞调用；沿用已有的线程池/异步封装、超时和错误转换方式。
5. 修改 API 时同时检查四处：后端路由/Schema、Web `frontend/src/api/`、小程序 `miniprogram/src/services/` 与类型、对应测试。
6. 流式对话接口使用 SSE。修改事件名、数据结构、终止事件或超时行为时，必须同步更新 Web 端解析器和小程序端兼容逻辑，并覆盖失败/断流场景。
7. 新快照 schema_version=4 必须嵌入完整 archive（包含剧本版本），恢复优先使用冻结正文；旧快照按 story_id 兼容读取后在下一次保存冻结，不得因内容包升级改变已开局案件。基础剧本只通过 manifest 与 android-base.json 白名单发布；Android 官方下载由受信签名目录与不可变内容包激活注册表，和基础本合并选取兼容版本。个人导入仅标为 imported、执行本地结构与可达性校验，不能冒充精选或覆盖基础/下载官方 ID。新制作人数为自动或指定 3—8，旧成品不强制改人数。
   会话持久化是可插拔的：默认内存存储；设置 `SESSIONS_DIR` 后使用 JSON 文件存储。新增状态字段时必须提供缺省值或迁移兼容逻辑。
8. 新开局玩家只分配非凶手角色。揭晓接口只允许终局访问，终局不可重新推进或指认；速推每轮需实际调查与发言（线索耗尽免调查），最后一轮允许补查。「返回搜证」只做本轮补查，下一轮必须经独立 next-investigation-round 动作推进。相关轮次字段须兼容旧快照缺省值。
9. SSE 回复由会话后台任务记录和保存，断流不能取消本轮记忆/历史写入；AI 回应期间拒绝并发游戏动作。文件存档需原子写入。
10. 单人游戏按玩家最终选择结案；确认后先持久化终局，不等待 AI 表决；人物判断只在用户请求 ballot-advice 时生成，使用揭晓前冻结的角色视图，失败则弃权且不改胜负。游戏阶段、投票、指认和揭晓的行为属于核心规则。改变阶段转换或胜负判定时，必须先补充或修改 `backend/tests/test_game_manager.py` 及相关服务/API 测试。
11. 剧本本人知识使用 `self_knowledge` / `objectives`；`cover_story` 仅为对外说辞，不能提升为事实；`solution` 证据映射在游玩中仅供作者审稿，终局可经揭晓接口展示证据链，不得自动把全知 `secret`、`backstory`、`alibi` 下发给玩家或无辜 AI。速推线索按 `discovery_round` 解锁，加载和生成须校验前置引用与循环依赖。
    新剧本的结构修复与证据一致性修复分别限次；按字段原子应用补丁，保留角色、线索 ID，禁止整表替换；仅在开局前允许纠正与真实行凶者不一致的真凶字段，之后必须重新审查身份与本人作案原文。所有修补结果必须重新通过结构与语义审查后才能保存，不对已开始的游戏自动改写剧本。
    新剧本负面审稿必须修稿，不得靠一次笼统复核放行。正面审稿须返回从真相识别的实际致死者 ID 和该角色本人作案知识原文，后端核对指定真凶与原文归属；制作结果 production 随正文原子保存；成品开局、旧档兼容读取、恢复与复盘不触发在线审稿或画像生成。审稿契约升级只影响新制作版本，不重新审查旧成品。
12. 定向质问可传 `target_id` / `presented_clue_ids`；出示证据须检查持有权并持久化公开状态，无辜角色应回应证据证实的本人经历。
13. 角色上下文统一由 `ContextAssembler` 生成；先权限筛选再检索，使用同一行动的冻结快照。事件和文书内容保留证言属性，不得因摘要、旧发言或模型推理自动升级为事实。
14. `discussion_events` 是权威对话记录，`discussion_history` 仅为公共兼容投影；新会话不再保存独立 `ai_memories`。SSE 先推送已记录并保存的问题（带 action_id/kind），客户端收到确认后才清除正文和本次出示的证据；询问对象沿用当前选择。失败前保留正文、对象和证据组合，讨论历史同样返回这两个可选字段，禁止重复乐观回显。AI 发言由逐句提交的 `segments` 拼成唯一正文，经来源及覆盖全部分句的一致性检查后才能推送/保存；迁移旧存档不得推断缺失的轮次、时间或来源。
    明确时间范围允许检查其中的子时点，分离时点不能合成范围；这只是时间来源约束，不得跳过每个具体动作的语义审查。
    分句审查同时提供完整句子上下文，保留未知语气的作用范围；不能因同句出现“不知道”而放过独立的行动断言。修复失败时只能引用可见证据或直接相关的本人原文，不能用无关秘密或重复掩饰代替对出示证据的回应。
    上下文序列化保持公共案情、本角色资料在前，动态轮次、公开状态、来源白名单和当前问题在后；工具定义不得随来源/候选人变化。权限与引用仍由后端检查。历史按时间顺序呈现，不能为缓存跨角色共享私密知识或复用过期权限；缓存命中只依据供应商实际 usage，固定前缀指纹不是命中证明。
15. 官方 DeepSeek V4 的剧本原稿保留低强度思考；审稿保留低强度思考，字段修补使用非思考 JSON 输出，仍执行全部结构、身份和语义校验。模型输入去重不得改变存档原文或丢弃部分引用。手机生成进度只报告真实阶段，不按等待时间推断百分比。
16. 面向玩家的文案以中文为主，保持现有游戏术语、阶段名称和错误提示风格；不要无理由改动既有文案或 API 字段的中英文命名。NPC 正文不得展示内部来源/角色编号或编码标记。玩家历史原文保持不变，展示层可将规范的询问/出示证据标记转为中文标签；不能擅自翻译玩家内容。

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
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

小程序验证：

```bash
cd miniprogram && pnpm install --frozen-lockfile
cd miniprogram && pnpm test
cd miniprogram && pnpm run typecheck
cd miniprogram && pnpm run build:weapp
```

没有专门的前端单元测试脚本时，至少运行受影响端的 lint、typecheck 或 build，并在最终说明实际运行过的命令。

## 配置、数据与安全

- 现有 Web/小程序部署的模型密钥只放在 `backend/.env`。安卓独立版按设计由用户在手机输入，由原生层使用 Android Keystore 管理的加密密钥保护 API key；不得复制电脑 `.env` 到 APK。不要提交 `.env`、API key、访问令牌或真实用户数据，不把密钥写入前端构建变量、游戏存档或日志。
- `npm run android:apk` 构建后自动执行 `scripts/audit-android-apk.py`，递归检查 APK / Chaquopy 归档并比对内置剧本和配图。发布前须检查通过；仅输出路径、校验值和结果，不输出密钥。可安装 APK 与 SHA-256 通过 GitHub Release 附件交付，不加入源码 Git。当前为开发签名预览版，提升 versionCode 时保留相同签名以支持覆盖升级。
- 启动时后端会校验必需的 LLM 配置；缺少密钥时的快速失败属于预期行为，不要通过硬编码默认密钥规避。
- `backend/assets/portraits/`、`backend/sessions/`、`backend/.port.json` 和各端构建产物属于运行时/生成文件，除非任务明确要求，不要提交。
- 处理剧本 JSON 时保留合法 JSON、UTF-8 编码和现有字段语义；不要把日志、推理过程或密钥写入存档。
- 不要为了“清理”而删除已有剧本、会话、肖像或用户改动；删除前必须确认目标和范围。

## 许可证与源码交付

- 当前项目许可证为 `AGPL-3.0-only`，根目录 `LICENSE` 保留 GNU 官方完整原文；三个 npm 项目的许可字段与前端锁文件根包字段保持一致。许可范围与历史版本边界见 `docs/licensing.md`。
- 第三方许可证、版权和归属声明按原许可保留，不将依赖许可统一替换为 AGPL；`licenses/Apache-2.0.txt` 用于历史版本及适用第三方材料，不代表当前项目默认许可。
- 发布 AGPL 版本的 APK/二进制时提供与其一致的对应源码、构建说明和许可证。部署供用户通过网络交互的修改版时，显著提供免费获取该部署版本对应源码的入口；上游仓库链接不能替代未发布的下游修改源码。
- 旧 Apache 版本、标签和 Release 不追溯改标。源码交付不得包含密钥、令牌或用户私有数据。

## Git 与交付规则

- 默认在独立分支开发，不直接改写已推送的共享历史，不对 `master` 强制推送。
- 提交信息沿用仓库已有的 Conventional Commits 风格，例如 `feat: ...`、`fix: ...`、`perf: ...`、`chore: ...`。
- 每次修改尽量小而聚焦；不要把格式化、依赖升级和无关重构混入功能修复。
- 提交或交付前检查 `git diff`、`git status`，确认没有密钥、构建产物、临时文件或意外生成数据。
- API、游戏规则、持久化格式或启动命令发生变化时，同步更新 README、类型、测试和本文件中受影响的说明。
- 最终报告应简要说明：改了什么、运行了哪些验证命令、是否还有已知限制或未验证部分。
