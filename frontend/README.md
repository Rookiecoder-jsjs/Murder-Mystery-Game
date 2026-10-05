# 剧本杀 Web 与安卓界面

[项目介绍与安卓下载](../README.md) · [完整开发指南](../docs/development.md)

本目录提供 React 19、TypeScript、Vite 8 界面。浏览器版通过 FastAPI 与 SSE 调用后端；安卓复用同一界面，通过 Capacitor 桥接 APK 内的 Python 引擎。竖屏首页、调查、对质和表决都有移动端布局。

## 本地开发

环境要求：Node.js 22.12+。在项目根目录按 [开发指南](../docs/development.md#环境与首次启动) 配置 Python 依赖与 `backend/.env`，然后执行：

```bash
npm --prefix frontend ci
npm run dev
```

只启动界面时，在本目录执行 `npm run dev`；仍需已启动的后端。Vite 读取 `backend/.port.json` 配置开发代理，前端地址以终端输出为准。

## 目录

| 路径 | 用途 |
| --- | --- |
| `src/pages/` | 首页与游戏页面 |
| `src/components/` | 阶段界面、案卷、对话和通用组件 |
| `src/context/` | 游戏状态与动作同步 |
| `src/api/` | 请求、SSE、安卓适配与数据类型 |
| `src/styles/` | 全局主题与移动端样式 |
| `public/brand/` | Logo、网页图标等品牌资源 |
| `android/` | 安卓原生桥接、模型设置与内容下载 |

业务组件通过现有 API 层调用，不分别实现请求。模型 API key 不应放在前端变量或构建资源中：Web 使用后端配置，安卓使用原生加密设置。

## 验证与构建

以下命令在本目录执行：

```bash
npm test
npm run lint
npm run build
```

`npm run build:android` 构建安卓页面，`npm run android:sync` 同步到原生工程。完整 APK 构建在项目根目录执行 `npm run android:apk`，构建后会运行密钥与内容审计。

安卓运行方式见 [实施记录](../docs/android-port-plan.md)，界面验收见 [UI 记录](../docs/android-ui-audit.md)，可独立下载的故事与配图见 [内容更新说明](../docs/story-content-updates.md)。
