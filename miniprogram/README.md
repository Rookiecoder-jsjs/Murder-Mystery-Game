# 剧本杀微信小程序端

这是现有 Web 前端之外的独立 Taro 客户端，复用同一套 FastAPI 后端和人物肖像资源。

## 本地运行

1. 启动项目后端，默认地址为 `http://127.0.0.1:8000`。
2. 在本目录执行 `pnpm install --frozen-lockfile`。项目已在 `pnpm-workspace.yaml` 中明确批准 Taro 所需的构建依赖。
3. 执行 `pnpm dev:weapp`，持续编译到 `dist/`。
4. 用微信开发者工具导入本目录（不是 `dist/`），工具会读取 `project.config.json`。
5. 本地联调时，在微信开发者工具中关闭“校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书”。

如后端不是 8000 端口，可在编译前设置：

```powershell
$env:TARO_APP_API_BASE='http://127.0.0.1:实际端口'
pnpm dev:weapp
```

真机无法把 `127.0.0.1` 解析到电脑；真机联调和正式发布阶段需要换成局域网地址或已备案的 HTTPS 域名。

## 验证命令

```powershell
pnpm run typecheck
pnpm run build:weapp
```

## CI 安装说明

CI 使用与本地一致的安装命令：

```powershell
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build:weapp
```

不要加 `--ignore-scripts`：Taro 的编译链依赖 `esbuild`、`@swc/core` 等安装期构建脚本。相关依赖的许可策略集中维护在 `pnpm-workspace.yaml`。
