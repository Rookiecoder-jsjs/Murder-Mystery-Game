# 生图与资源更新

## 图像调用

读取环境当前提供的 `imagegen/SKILL.md`，使用内置工具。工具名可能为 `image_gen__imagegen`；不要猜测不可用的工具。输出形状以工具实际结果为准，先查看小段元数据获取本地路径，不打印整段 base64。

一部新故事产出一张公开场景封面和 N 张角色画像，N 等于角色总数，包括凶手，受害者不计入。每张独立调用，避免生成拼贴后裁切或混用角色。依赖顺序为正文与公开外观确定 → 提示词清单 → 生成 → 目视检查 → 编码 → 角色ID映射。

内置工具支持的参数以当前工具 schema 为准。在当前 functions 执行器中可按以下方式生成一张新图；新图不填写参考图片参数，编辑本地图时先用 view_image 查看，再使用实际支持的 referenced_image_paths。

```javascript
// @exec: {"yield_time_ms": 120000, "max_output_tokens": 300}
const result = await tools.image_gen__imagegen({
  prompt: "这里填写一张资源的精确公开美术提示词",
  transparent_background: false
});
generatedImage(result);
```

工具运行中如返回 cell_id，按其约定使用 wait，不另起重复请求；模型可控制等待时仍需提供进度。一次主题创作不应因为图像生成等待而结束为“后续再做”。工具失败时保留已完成图像和记录，明确缺失的角色，遵守 imagegen 的回退授权要求。

## 提示词隔离和一致性

只取公开场景、公开身份、年龄/性别（已设定时）、服装和外观美术设计。不要提交 `true_killer/is_killer`、secret、self_knowledge、motive、solution、全稿或隐藏作案物；场景图也不绘制能提前暴露真相的证据、尸体摆法或秘密通道。图片不是可调查证据。

全套保持 Art Deco Noir / 案卷气质：绘画感电影光影、炭灰/暖褐/象牙色、轻纸张纹理。时代服装与用户主题一致，现代/科幻主题不要被强制改成民国。脸部清晰，各角色采用相近照明、中性表情，避免只给凶手阴影、凶恶表情或武器。外观未由正文指定的细节记为美术设定，不承担推理功能。

封面建议横版3:2，场景一眼可识别，主体留在中央安全区，无文字、标志或水印。画像建议竖版2:3，单一成年人、胸像、头顶留白、脸在中央，避免手部或复杂道具遮脸。头像会圆形裁切，因此关键信息不能放在四角。

示例提示结构，用实际主题和公开身份替换：

```text
Use case: illustration-story
Asset type: murder mystery game character portrait, portrait 2:3
Primary request: one adult character, [公开身份与外观]
Scene/backdrop: [公开时代和环境，简单背景]
Style/medium: painterly cinematic Art Deco Noir, charcoal/warm sepia/ivory
Composition/framing: chest-up, complete head with margin, centered clear face
Lighting/mood: neutral dignified expression, readable face, consistent soft light
Constraints: no text, logos or watermark; no weapon, guilt cues or secret evidence
```

逐张检查人数、脸部、时代、服饰、构图、风格及泄底风险。修正语义或图像内容仍用 imagegen，Python 只做等比例缩放、格式编码和哈希统计。

## 文件和清单

生成图原稿通常保留在工具返回的 `$CODEX_HOME/generated_images/...` 路径。把选定成品落到项目，不引用工具目录或临时云 URL。用本 skill 的工具编码，不覆盖已有目标：

工具需Python3.11+与Pillow。优先使用当前环境已有的文档/图像Python运行时；Codex桌面可用 `load_workspace_dependencies` 查找，不把本机解释器绝对路径写进skill。默认Python缺少Pillow时换到已有运行时，而不是为编码改用图像API。

```bash
python3 <skill-dir>/scripts/story_tools.py encode --input <returned-image-path> --output backend/app/content/images/<uuid>/cover-v1.webp --kind cover
python3 <skill-dir>/scripts/story_tools.py encode --input <returned-image-path> --output backend/app/content/images/<uuid>/char_1-v1.webp --kind portrait
```

当前项目成品规范：封面960×640，画像640×960，WebP质量85、method6；脚本拒绝比例差异超过1%的图，不偷偷裁掉主体。需要改构图时先用 imagegen，或按用户明确的裁切要求实施。新版资源使用未占用的版本化文件名。

顶层 `artwork` 的示例结构如下，版本应按本次实际内容调整：

```json
{
  "version": 1,
  "cover": "cover-v1.webp",
  "portraits": {"char_1": "char_1-v1.webp"},
  "retained_files": []
}
```

portraits 必须覆盖所有实际角色 ID，不能按数组次序猜测。更换基础/Web图片时，把不再活跃的旧文件名加入 `retained_files` 并保留字节；历史下载包也保持不可变。现有cover-v2可继续被v3引用，不因内容版本变更重复生成未修改的图。

建立 `docs/story-artwork-<date>-<short-batch>.json`，避免覆盖已有提示集。逐图保存故事ID/标题、角色ID/姓名（封面无角色）、精确提示词、内置工具标识、生成时间、返回原图文件名、最终项目相对路径、尺寸、字节数和SHA-256。不得把 key、私人路径凭据或全稿写进此清单。只有提示实际做到隔离时才记录 `private_story_sent=false`。

## 验收

`story_tools.py check` 在非 draft 模式要求封面和全部画像存在，并检查所有保留资源、WebP格式、尺寸上限与完整解码。它不自动证明视觉质量。抽看图仍须 view_image。

浏览器/手机验收检查公开封面、玩家头像、其他 N-1 人头像的ID/姓名对应、圆形裁切及竖屏溢出。设备已连接且测试获准时使用正常“检查更新/下载/更新”操作，保留 key 和旧档；不卸载、清数据、锁屏或向玩家局发言。只打开序幕的验证应准确称为本地开局与图片验收。
