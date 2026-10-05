# 内容更新协议示例

这是 [内容独立更新设计](../../story-content-updates.md) 的字段示例，不是发布产物。全零哈希、source_commit 和文件大小均为占位；所列 Release/附件尚未创建，不能拿这些文件进行安装或宣称已经发布。

- `catalog.payload.example.json`：公开目录的未签名 payload。人物和真相正文不进入目录。
- `bundle.payload.example.json`：同一故事的包清单 payload，演示纯文字包；有配图时在 files 中增加 `images/<合法文件名>.webp`，内层 package.json 的 artwork 引用必须与之匹配。

真实发布时，构建工具从实际文件计算大小与 SHA-256，并填写含该内容的固定源码提交。两个 payload 分别生成 UTF-8 原始字节，在固定域前缀后签名，再封装成设计文档的 Base64 签名信封。目录信封保存为 `content/catalog.json`，清单信封作为 ZIP 内的 `bundle.json`；不能直接把这里的 payload 当信封使用。

目录哈希覆盖最终完整 `.mmstory`。包清单只覆盖 ZIP 内除 bundle.json 以外的白名单文件，不能把包自身或其签名加入自己的哈希清单。发布私钥、APK 签名私钥与 API key 均不能进入示例、仓库或内容包。
