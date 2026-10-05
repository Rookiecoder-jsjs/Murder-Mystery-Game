# 签名内容包与手机更新

本文件仅在交付需要官方发布时读取。具体权限来自用户请求和已有会话授权；skill 不自动授权推送、上传或手机操作。

## 读取当前状态

当前实现的可信来源：

- `content/config.json`：固定目录入口、发布者、受信公钥、允许下载主机。
- `content/catalog.json`：当前已发布签名目录；验证信封后读取 catalog_revision 和各故事 content_version，不能把 Base64 解码当作验签。
- `scripts/package-story-content.py`：既有离线打包/签名/版本及不可变字节规则。
- `docs/story-content-updates.md`：客户端安装链路、实际发布状态及验收边界。

不要硬编码“下一次为r4”。先验证当前目录，检查远端发布状态和本地缓存。可用发布脚本的 `verify_envelope` 与 `content/config.json` 公钥验证 `MMG-CATALOG-V1` 域，离线读取需OpenSSL，不需要模型key。不要改目录URL、公钥或Android基础白名单来迁就发布。

新故事从 content_version1开始；已发布的正文、JSON元数据或图片改变必须提高 metadata.version。catalog_revision 对本次整个官方目录递增，和各故事版本独立。

## 先做完整本地成果

1. 作者自检、结构/证据可达性、图片映射/解码、受影响回归通过；记录真实模型审稿和实玩是否完成。未完成真实体验评审的内容不能宣称正式精选质量验收通过，若用户授权发布体验预览，目录说明必须准确。
2. 检查源码和待打包白名单，仅含公开故事、图片、许可与出处。排除 `.env`、key、令牌、签名私钥、用户SQLite/存档/日志。不要输出凭据进行“核对”。
3. 完成可审查 diff，更新必要文档，按已授权分支规则提交正文和资源，取得固定40位源码SHA；不用工作区占位值。遵守项目AGPL对应源码和第三方归属要求，保持固定提交可获取。
4. 先运行默认 dry-run 得到报告；使用单独输出目录，避免覆盖当前签名 catalog/report 缓存：

```bash
python3 scripts/package-story-content.py --output dist/story-content-dry-run
```

打包器会调用共享的无依赖 staged Python 验证；不调用模型、也不自动上传。

## 签名与旧字节复用

使用现有受信公钥对应的仓库外私钥。路径从用户或已知本地发布环境取得，不提交私钥路径配置，不复制密钥到skill/仓库/包中，不打印私钥。缺失时停在可发布的本地成果，明确所缺条件，不能另造新key让手机无法验签。

准备上一份已验证签名目录与旧 `.mmstory` 原始字节，放到新的输出目录中。未变化故事必须复用上次公开包的原字节、签名、来源提交与下载URL；不能以新的源码SHA重打所有旧包。旧包缺失时从已验证目录指定的官方地址获取并核对长度/哈希，不用任意镜像。

```bash
python3 scripts/package-story-content.py --output <release-output> --revision <next-catalog-revision> --source-commit <fixed-40-char-sha> --signing-key <outside-repo-key-path> --previous-catalog <previous-signed-catalog>
python3 scripts/tests/test_story_publisher.py
```

查看 report 中 changed/reused、文件白名单、包长度与SHA。版本冲突必须提高真实内容版本；不能删除缓存或提高目录号规避同故事同版本冲突。

## 外部发布顺序

授权已明确时继续执行，不重复索取同一授权；没有授权时交付上述成果和明确的发布动作供最后批准。不得在未经授权的外部写入之前先暂停所有本地制作。

1. 上传新包到固定 `content-r<revision>` Release，并提供该批 signed catalog/report。使用现有GitHub CLI/API，按官方当前API规范核对操作；工具缺失时不要编造成功。
2. 内容Release不要抢占应用最新版入口；API的 make_latest 为字符串 `"false"`。保持现有内容预览标识策略，不改历史Release附件，不覆盖不可变包。
3. 从公开远端逐个下载新包，核对签名目录规定的完整长度与SHA，验证ZIP签名、白名单和文件清单；尽量运行仓库实际Android ContentVerifier/JVM测试。不能只检查HTTP200或附件名。
4. 远端附件全部可用且正确后，才把该批已签名 catalog 原字节写到 `content/catalog.json`，提交并按授权推送目标分支。首次正文源码提交与最后目录切换是两个不同步骤；仅推故事JSON不能让手机发现新版。
5. 验证手机所用官方目录入口返回的新目录仍验签通过，旧条目仍指向原字节，新增条目指向存在的新包。发布中断时保留已有可用目录；重试先检查已有固定标签/附件的字节是否相同，不盲目重复创建、覆盖或删除Release。

包上限、ZIP安全和受信主机等具体限制沿用打包器与Android verifier；不复制另一套验签规则。遇到自动审批拒绝时不绕过拒绝，保留未受影响的成果并准确说明被拒动作和原因。

## 手机行为与验证边界

首个支持该格式的客户端已装好后，兼容故事和配图更新不重构 APK。基础包仍由 android-base.json 白名单构建；Web读取源码manifest。改变引擎、界面或不兼容格式时才另做APK升级，不能把引擎代码塞进故事包。

手机用户点“检查更新”，从已验证目录看到“下载/更新”后手动安装；首页挂载或应用恢复超过当前实现阈值时只自动检查目录，不自动下载。具体时间阈值以 `StoryLibrary.tsx` 当前代码为准。下载不需要模型key，AI对话才请求模型。

获准且设备解锁时可通过正常UI安装；核对新局的内容版本、人数和图片，而旧局公开状态、历史和冻结引用不变。保存配置状态或加密配置文件哈希，不读取/打印key。覆盖升级仅在确需新APK且同签名时进行；不要卸载、清数据或执行锁屏。

最终分别报告本地制作、签名打包、远端发布、手机安装、真实模型完整游玩的实际状态。不要用“已经更新”含混地覆盖未完成环节。
