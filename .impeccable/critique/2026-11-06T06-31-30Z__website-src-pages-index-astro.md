---
target: website/src/pages/index.astro
total_score: 24
max_score: 36
na_heuristics: 9
p0_count: 2
p1_count: 2
target_identity: "file:/Users/guoxudong/sectrend/pluvy/website/src/pages/index.astro"
target_fingerprint: "sha256:fbed3087bdf3408566cbd3dcf0a68145be25a4de3fc8c7344f4982c6376c7b20"
target_path: /Users/guoxudong/sectrend/pluvy/website/src/pages/index.astro
timestamp: 2026-11-06T06-31-30Z
slug: website-src-pages-index-astro
---
Method: dual-agent (A: e975337e/a21ac3d2 · B: e975337e/9b5af795)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 各 section 的 [data-reveal] 在进入视口 32% 前保持 opacity: 0，打印或导出 PDF 时几乎是空白页 |
| 2 | Match System / Real World | 3 | 退出码 2 被写成"Cannot conclude"，文档里的含义是配置、编码、文件系统或 Git 失败；"Choose one scope"缺少对象 |
| 3 | User Control and Freedom | 3 | WebGL 背景动画一直以 30fps 运行，不能暂停 |
| 4 | Consistency and Standards | 2 | 5 个文案不同的链接都指向 docs/getting-started/；站内链接也带外链符号 ↗；主按钮有墨色和酸性绿两种样式 |
| 5 | Error Prevention | 3 | 风险很低 |
| 6 | Recognition Rather Than Recall | 2 | 页面上没有安装命令，也没有任何一条 finding 输出示例 |
| 7 | Flexibility and Efficiency | 2 | 代码块不能复制；没有链接到 checker 参考 |
| 8 | Aesthetic and Minimalist Design | 3 | 整体克制、有自信；但首屏 CTA 下面有大约 390px 空白，装饰层还压在正文上 |
| 9 | Error Recovery | n/a | 落地页没有错误状态 |
| 10 | Help and Documentation | 3 | 文档有深度，但中文页的 CTA 进入英文文档，/zh/docs/getting-started/ 返回 404 |
| **Total** | | **24/36** | **Acceptable（67%）** |

## Design Specificity Verdict

LLM assessment：品牌是自己的，页面骨架是通用模板。"A gate, not an editor."、鳄鱼和鸟的点阵动画、深色 POLICY/RUN 证据面板，这三样是 Pluvy 独有的。但首屏主张"Engineering standards, enforced without rewriting your code"，换成 Semgrep、Sonar 也一样成立；版式是常见的开发者工具模板（大标题 → 三条原则 → 深色代码块 → 三列指标 → 收尾大 CTA）。i18n.ts 里 "agent" 出现 0 次，PRODUCT.md 里写的主要用户和定位在页面上完全看不到。字体全用系统字体，没有加载 webfont，所以这套视觉只在 macOS 上成立。

Deterministic scan：对 .astro 源码的扫描结果是 exit 0，但只做了正则匹配，元素级规则没有运行，不能当作"干净"。URL 扫描：en 桌面端 4 条 primary（italic-serif-display、oversized-h1、undersized-ui-text×2），en 移动端 7 条，zh 移动端 8 条（多出 justified-text）。有 [data-reveal] 的 section 因为 opacity 为 0 被检测器跳过；强制显示后，每页又多出 3 条 italic-serif-display。

误报：hero 上的 italic-serif-display（标题本身是无衬线，只有 em 是衬线体）；zh 标题的 italic-serif-display（Iowan 字体没有 CJK 字形，实际不会生效）；oversized-h1（CTA 完整位于首屏内）；evidence-block 标题栏的 undersized-ui-text（属于终端外框，本应豁免）；zh 的 justified-text 被规则自己的 CJK 豁免说明否定，不过中英混排确实出现了 +22% 的字距拉伸。

真问题：移动端导航只有 10.4px，点击区域约 25×33px（SiteHeader.astro:222）。

Visual overlays：注入在无头浏览器里成功，但没有用户可见的 [Human] 标签页。

## Priority Issues

[P0] 页面没有告诉主要用户"这是给你的"。i18n.ts:5-11、index.astro:14。修复方向：保留"A gate, not an editor."，在首屏说明里写清"代理写代码，任务结束时由门禁检查，只读，exit 1 表示停止"。命令：/impeccable clarify。

[P0] 装饰 canvas 压在正文上，还画到了页脚上面。LandingBackground.astro:14-20、SiteFooter.astro:30-33、Principles.astro:47-52。修复方向：给页脚加 position:relative 和 z-index:1，或者把背景挪进 main；在文字列区域对 canvas 做遮罩或降低透明度；去掉 text-shadow 补丁。命令：/impeccable layout 或 /impeccable quieter。

[P1] 证据面板里没有证据。Workflow.astro:12-17 展示的是 "checkers": {}。修复方向：换成真实的策略片段（参考 examples/.pluvy/pluvy.json），再加一块 finding 输出面板。命令：/impeccable clarify 或 /impeccable shape。

[P1] 一个目标、五种标签；中文页的入口进入英文文档。Hero.astro:24、Workflow.astro:27、FinalCta.astro:18、SiteHeader.astro:26、SiteFooter.astro:21。修复方向：让不同 CTA 指向不同目标；发布中文 getting-started，或者把入口如实标成英文指南。命令：/impeccable clarify。

[P2] 可访问性：深色主题下 .button--acid 的焦点环对比度约 1.15:1；h1、h2 的可访问名称粘连（"standards,enforced"）；.exit-codes 的 aria-label 没有 role；移动端导航 10.4px，320px 宽时被截断。命令：/impeccable audit 或 /impeccable harden。

## Persona Red Flags

Jordan（新手）：页面上没有安装命令，也看不到 finding 长什么样，只能去看 README。

Riley（怀疑者）：看到 "checkers": {} 会认为是占位演示；页脚被点阵覆盖，对卖"严谨"的产品是很坏的信号；"No error findings"掩盖了"只有 warning 时也返回 0"这一点。

Casey（移动端）：标题被硬换行切成 6 行；WebGL 在 DPR 2 下全程 30fps；导航点击区域约 25×33px。

工程负责人（评估 AI 代理护栏）：看不出产品和代理有关，也没有 CI 示例；"Pluvy 只报告，是否放行由集成决定"这个边界没有写在页面上。

## Minor Observations

- Capabilities.astro 和 BlogPreview.astro 已经写好，但两个落地页都没有引用。
- 三条命令只有第一条带 $ 提示符。
- 等宽标签只有 0.65rem（10.4px）。
- 没有 og 和 twitter 卡片元信息，也没有 en/zh 之间的 hreflang。
- 优点：reduced-motion 有三处处理，skip link 可用，正文对比度全部达到 AA。

## Questions to Consider

- 如果首屏写的是"Your agent says it's done. Check it."，页面上还有哪些内容需要保留？
- 鸟啄鳄鱼最能表达"门禁会咬人"，为什么藏在 26 秒循环的背景里？
- 换成真实的边界规则和真实的 finding 之后，三条原则还需要吗？
