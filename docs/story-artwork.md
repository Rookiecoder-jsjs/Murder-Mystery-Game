# 内置剧本配图（2026-10-03）

首批三个原创本配齐 3 张场景封面、15 张人物肖像。使用 Codex 内置 imagegen 生成，未调用 DashScope，也未读取或消耗项目内的生图密钥。构图统一为民国上海、电影光影与暖灰案卷质感；只使用公开场景、身份及美术外观，不把真相、秘密、动机或凶手标签交给图像模型。外观属于美术设定，配图不是推理证据。

资源位于 `backend/app/content/images/<story_id>/`。封面为 960×640，头像为 640×960，均由生成图编码为 WebP（质量 85），18 张共 1,171,744 字节，约 1.12 MiB。原始图由生成工具保留。提示词与资源对应表见 [生成记录](story-artwork-prompts.json)。

数据包顶层 `artwork` 描述公开视觉资源，示例：

```json
{
  "artwork": {
    "version": 1,
    "cover": "cover-v1.webp",
    "portraits": { "char_1": "char_1-v1.webp" },
    "retained_files": []
  }
}
```

只由 manifest 列出的内置数据包应用该清单，普通 JSON 导入忽略配图声明和原肖像 URL。文件名只能是安全的单层 WebP 名称，角色 ID 必须存在。列表增加可选 `cover_url`，角色继续使用已有 `portrait_url`，兼容无配图旧内容。

Web 开发环境经 Vite 代理至 FastAPI 的 `/assets/story-library` 静态目录；生产前端构建也按清单复制图片。Android 相同构建把图片放入 Capacitor 本地资源，直接从 `https://localhost/assets/story-library/...` 读取，无需 HTTP 后端、电脑连接或 DashScope key。Python 只读取包的映射，不复制一份图片到手机数据库。小程序复用服务端资源 URL；微信真机显示尚未验证。

新开内置局冻结角色的图片 URL。已开局的旧快照不改写，之前无配图的旧局仍可能显示首字头像；可新开一局查看完整配图。图片升级使用新文件名，并将旧文件名加入 `retained_files`、保留原文件，以让历史快照 URL 继续可用。不要在不增加文件名版本时覆盖图片。当前更新渠道仍为 APK 或后端发布，未实现远程图片包更新。

验证：全部 18 张与 APK 内文件逐字节一致；Redmi 真机 WebView 全部解码成功，来源均为本地 `https://localhost`。首页三张封面与雨夜开场角色头像显示正常，无水平溢出。只读取已有游戏和打开现有序幕，没有发言、投票或推进该局。更新前 12 个游戏的公开摘要仍保留，四个此前完成的测试局的状态、线索、历史和揭晓一致。运行期间出现另一局新雨夜存档，总数为 13；全局 revision 的变化与游戏业务内容分开核对。文字模型配置仍为 configured，未读取密钥。

最终验证：后端 320 项通过；原生 Python 4 项、Web 5 个测试文件通过，Web lint、Android TypeScript/Vite 构建、小程序 typecheck 和微信构建通过。新增检查包括全部内置资源存在、WebP 类型、快照图片 URL 保留、导入不能冒充内置配图，以及路径和无效角色拒绝。最终 APK SHA-256 为 `215173ea42e656db1926d4780d778eb8c940f420b180776e651d0984953eaabf`。宿主 Python 3.11 的历史预编译警告仍存在，Gradle 构建成功且已在手机实际运行。

最终版本覆盖安装及冷启动后，13 个游戏摘要均保留，四个完成测试局的完整公开业务内容与揭晓仍一致；全部 18 张图片再次解码成功且与最终 APK 资源一致。临时 WebView 调试转发已移除，未执行锁屏。

## 后续 DashScope 接入

内置配图已完成，不再在线生成。电脑版现有 `PortraitService` 使用 `qwen-image-3.0` 异步提交、轮询及本地落盘，接口与 [阿里云 Qwen-Image-3.0 官方文档](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference) 核对一致；真实 key 的鉴权、可用地域和实际生成效果尚未验证。

安卓版目前仍关闭在线生图。下一阶段需独立的原生生图设置及加密密钥存储，不能把文字模型 key 当作 DashScope key，也不能将 key 传给 WebView、Python、剧本包或日志。提交任务前持久化 task_id，应用重启恢复轮询，下载后的图片保存在应用私有目录并由原生资源映射提供给 WebView；临时云图片链接不作为最终存档 URL。

仅新生成的个人剧本异步补齐肖像，失败提供单张重试，缺图继续使用首字头像，图片生成不阻塞进入游戏。已有图片、内置本、开局、继续存档均不重复生成。凭据及 endpoint 必须属于同一地域，变更服务配置时不能混用旧任务的凭据。后续填写真实 key 后才能完成在线联调，目前没有声称安卓 DashScope 已接通。
