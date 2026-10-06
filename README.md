<p align="center">
  <img src="frontend/public/brand/logo-casefile-v2.png" width="72" height="72" alt="剧本杀 Logo" />
</p>

<h1 align="center">剧本杀 · Murder Mystery Game</h1>

<p align="center"><strong>一个人入戏，与 AI 角色对质，凭证据找出真凶。</strong></p>

<p align="center">
  <a href="https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/tag/v1.0.0-android-preview.5"><img src="https://img.shields.io/badge/Preview-1.0.0--preview.5-A93025?style=flat-square" alt="安卓预览版 1.0.0-preview.5" /></a>
  <a href="#安卓开始游玩"><img src="https://img.shields.io/badge/Android-7.0%2B-3DDC84?style=flat-square" alt="Android 7.0 及以上" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--only-blue?style=flat-square" alt="许可证 AGPL-3.0-only" /></a>
</p>

<p align="center">
  <a href="https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/download/v1.0.0-android-preview.5/Murder-Mystery-1.0.0-preview.5-arm64.apk">下载安卓 APK</a> ·
  <a href="#怎么玩">游戏玩法</a> ·
  <a href="#电脑运行">电脑运行</a> ·
  <a href="#开发与扩展">开发文档</a>
</p>

一款单人 AI 剧本杀游戏：你扮演案件中的一名角色，其他角色由 AI 扮演。搜集线索、核对证言，作出你的最终指认。

**手机安装 APK、填写自己的 API key，就能直接玩，无需电脑或自建服务器。** AI 对话与新剧本生成需要联网，消耗所配置供应商的 API 额度。

<table>
  <tr><th>原创案件的场景配图</th><th>安卓真机角色界面</th></tr>
  <tr>
    <td align="center">
      <img src="backend/app/content/images/ad60c7e0-1f56-4fc3-bcaa-705910d03301/cover-v1.webp" width="300" alt="雨夜的最后一声钟：报馆场景封面" /><br />
      <sub>雨夜的最后一声钟</sub><br /><br />
      <img src="backend/app/content/images/ad60c7e0-1f56-4fc3-bcaa-705910d03306/cover-v2.webp" width="300" alt="终场之前的返场：剧院场景封面" /><br />
      <sub>终场之前的返场</sub>
    </td>
    <td align="center">
      <img src="docs/images/android-characters.png" width="200" alt="安卓竖屏实机截图：序幕阶段的角色画像与公开身份列表" />
    </td>
  </tr>
</table>

## 安卓开始游玩

[下载 1.0.0-preview.5 APK](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/download/v1.0.0-android-preview.5/Murder-Mystery-1.0.0-preview.5-arm64.apk) · [发布说明、校验值与对应源码](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/releases/tag/v1.0.0-android-preview.5)

1. 安装 APK，在「我的 → 模型设置」，填写 OpenAI 兼容的 HTTPS 服务地址、API key 与模型名称；可使用默认的 DeepSeek 配置。
2. 在「剧本库 → 可开局」选本，进入详情选择模式；第一次建议选择三人本和速推模式。
3. 想玩更多案件，在「剧本库」检查更新并搜索故事，进入详情下载；下载剧本不需要模型密钥。
4. 游戏自动保存，退出后可从首页继续，结案后可查看复盘。

APK **不内置 API key**，由你在手机填写并加密保存。当前为开发签名预览版，仅提供 **arm64-v8a、Android 7.0 及以上**安装包；同签名覆盖升级保留配置与存档，卸载会删除本地数据。

## 功能特点

- **预制案件**：六个原创剧本，配齐封面与角色画像；选本开局无需重复生成、审稿或生图。
- **角色对质**：每人有独立资料与知识范围，支持自由提问、定向质问和出示证据。
- **动态人数**：按故事安排 3—8 名角色，包含一名玩家，其余由 AI 扮演。
- **内容更新**：安卓可独立下载新剧本与配图；兼容内容无需重装 APK，已开始的游戏保留原版。

## 怎么玩

**阅读本人剧本 → 搜证 → 对质 → 表决 → 真相与复盘**

你得到的是自己的身份、经历和任务。调查获得线索后，可以选择角色并出示证据，核对对方说法。确认最终指认后立即结案，查看真相与证据链。

| 模式 | 适合什么体验 |
| --- | --- |
| 速推 | 三轮推进，每轮调查并发言，再进入下一轮；适合初次游玩 |
| 经典 | 自由调查和多轮讨论，适合慢慢梳理人物关系与证据 |

## 选一个案件

角色数包含玩家，其余由 AI 扮演。安卓版随 APK 提供前三本，后三本通过官方内容包下载；Web 版读取全部六本。

| 剧本 | 人数 | 案件切入点 |
| --- | :---: | --- |
| 雨夜的最后一声钟 | 3 | 暴雨封住小报馆，一声钟成了共同的不在场证明 |
| 白鹭旅馆的无字药瓶 | 5 | 寿宴后，一瓶胃药与五个人经手的托盘 |
| 雾港双重提货单 | 7 | 同一批货、两张提货单，核对七个人的时间线 |
| 玻璃花房的空白铭牌 | 4 | 泥地脚印与空白铭牌，为什么指向同一个名字？ |
| 潮汐之前的晚宴 | 6 | 旧渡轮上的合照，能否证明房里的人仍然活着？ |
| 终场之前的返场 | 8 | 义演发生坠落，危险是什么时候进入舞台的？ |

首次建议体验前三本。后三本已配齐封面和画像，目前仍为体验预览，完整真实模型与玩家评审尚未完成。

想玩自己的主题？使用「我的 → 生成新故事」，由故事决定人数或指定 3—8 人。新稿需要生成、审稿和必要修补，耗时与质量受模型影响，**不保证达到精选本的完成度**。安卓版自行生成剧本的在线画像功能尚未接入。

## 电脑运行

Web 版在电脑运行 Python 后端与浏览器界面。完整配置、Windows 启动及 APK 构建见 [开发指南](docs/development.md)。

<details>
<summary>从源码启动 Web（Python 3.11+ / Node.js 22.12+）</summary>

以下以 Linux / macOS 为例，需要自己的模型 API key。

```bash
git clone https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game.git
cd Murder-Mystery-Game
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
cp backend/.env.simple backend/.env
# 编辑 backend/.env，填写 DEEPSEEK_API_KEY 并核对模型名称
npm run dev
```

打开终端显示的前端地址，通常为 `http://localhost:5173`。如需重启后继续 Web 游戏，在 `backend/.env` 设置 `SESSIONS_DIR=sessions`。

</details>

## 开发与扩展

| 你想做什么 | 从这里开始 |
| --- | --- |
| 配置、测试、API 与构建 APK | [开发指南](docs/development.md) |
| 了解 Web / 安卓 / 小程序分工 | [前端说明](frontend/README.md) · [安卓实现](docs/android-port-plan.md) · [小程序说明](miniprogram/README.md) |
| 制作与更新故事 | [剧本包格式](docs/story-library.md) · [内容更新链路](docs/story-content-updates.md) |
| 按主题创作并生成配图 | [本项目的剧本更新 skill](skills/update-mystery-stories/SKILL.md) |
| 理解角色知识与上下文 | [AI 上下文说明](docs/ai-context.md) |
| 查看已完成的验证与已知问题 | [首批实玩记录](docs/builtin-story-playthrough.md) · [配图记录](docs/story-artwork.md) · [移动 UI 验收](docs/android-ui-audit.md) · [新版首页与剧本库](docs/android-lobby.md) |

欢迎通过 [Issues](https://github.com/Rookiecoder-jsjs/Murder-Mystery-Game/issues) 反馈问题或提交 PR。反馈时附上平台、应用版本和复现步骤即可。

## 许可证

当前源码采用 [AGPL-3.0-only](LICENSE)。允许商用；分发及通过网络提供修改版时的对应源码要求、历史版本边界和第三方许可见 [许可说明](docs/licensing.md)。
