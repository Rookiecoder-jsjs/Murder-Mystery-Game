# 项目 Logo · 案卷搜证

![剧本杀 Logo](../frontend/public/brand/logo-casefile-v2.png)

用户选定第二轮 A 方案：红底、米白案卷与黑色放大镜，表达阅读剧本、搜证和发现关键线索。颜色沿用当前报纸界面的印章红、纸面米白与油墨黑。图形不放小字，与现有名称「剧本杀」组合使用。

## 原图与派生资源

- 原图：`docs/brand/logo-casefile-source.png`，1254 × 1254 PNG，内置 image_gen 生成。
- Web：首页标识 `frontend/public/brand/logo-casefile-v2.png`（512px），favicon `favicon-v2.png`（48px）。
- Android：五种密度的普通、圆形、自适应图标及现有尺寸的启动图；自适应前景108dp，原图居中缩至72dp，将红底边缘延伸到外侧以避免方形接缝。
- 资源构建：`python3 scripts/build-brand-assets.py`，需要 Pillow。仅进行尺寸转换、边缘延伸和圆形遮罩，不重新生成图稿。
- 所有派生资源提交到源码，普通 APK 构建不需要生图 API 或 Pillow；均不含密钥。
- PNG 是位图源，不冒充 SVG。正式发布仍需按目标系统遮罩检查；本版保留开发签名。

第一轮面具与第二轮 B 方案未采用，不随应用打包。

## 原始生成提示词

```text
Use case: logo-brand
Asset type: premium mobile game app icon, one finished square artwork.
Primary request: create an exceptionally polished, original icon for a Chinese literary murder-mystery roleplaying game. Its visual language is warm newspaper paper, ink and vermilion editorial marks. The idea is "an unsolved case file": an ivory case-file sheet, with a cleverly integrated circular magnifying lens in the lower half. The lens is a clear large black circle with ivory center; its diagonal handle becomes part of the folded document edge, rather than a separate clipart object. A single bold red editorial slash inside the lens signals a discovered clue. Abstract and editorial rather than literal office stationery.
Design quality: boutique independent game identity, disciplined Swiss graphic design meets Chinese newspaper noir. Distinctive asymmetry, optical balance, bold silhouette, generous breathing room. Flat clean shapes, subtle thoughtful paper layering at most. No childish illustration, no mascots.
Composition: warm vermilion #b3382c full-bleed square background. A compact warm ivory #f4f1ea document-and-lens symbol centrally placed, occupying 60 percent of the width; one ink-black #1a1a1a lens accent. All important artwork safely inside the central 65% for mobile icon crops. Crisp strong edges, no exterior rounded border; system will mask icon corners.
Text: none. No words, letters, labels, numbers, watermark or presentation board.
Avoid: theatrical masks, angry eyes, skulls, blood, weapons, robots, stars, generic AI imagery, fake 3D, excessive shadow, glossy gradients, hairline detail, complex newspaper copy. Output exactly one icon, no mockup.
```
