---
target: website/src/pages/index.astro
total_score: 19
max_score: 36
na_heuristics: 9
p0_count: 0
p1_count: 3
target_identity: "file:/Users/guoxudong/sectrend/pluvy/website/src/pages/index.astro"
target_fingerprint: "sha256:fbed3087bdf3408566cbd3dcf0a68145be25a4de3fc8c7344f4982c6376c7b20"
target_path: /Users/guoxudong/sectrend/pluvy/website/src/pages/index.astro
timestamp: 2026-11-06T07-36-23Z
slug: website-src-pages-index-astro
---
Method: dual-agent (A: d26972d9 · B: 3fabf1ea)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 主题状态只用图标表示；长页面没有位置提示 |
| 2 | Match System / Real World | 3 | 真实命令、真实输出；但 gate、finding、scope 在定义之前就用了 |
| 3 | User Control and Freedom | 2 | 背景动画只能靠系统的减弱动态设置停掉；页头是 absolute，滚动后没有导航 |
| 4 | Consistency and Standards | 2 | 落地页和文档的主题控件不同；语言切换只在落地页有 |
| 5 | Error Prevention | 2 | 页面上的策略与"示例策略"链接打开的文件不同 |
| 6 | Recognition Rather Than Recall | 1 | 没有安装命令、Python 3.12 要求、许可证和 CI 片段 |
| 7 | Flexibility and Efficiency | 1 | 对已决定用的人没有可复制的安装行或 CI 步骤 |
| 8 | Aesthetic and Minimalist Design | 3 | 克制；Principles 左栏大块空白；首屏装饰仍压字 |
| 9 | Error Recovery | n/a | 静态落地页没有错误状态 |
| 10 | Help and Documentation | 2 | 文档一键可达，但页面本身不解释术语 |
| **Total** | | **19/36** | **Acceptable（53%）** |

上一轮是 24/36，但两轮的评审员不同，这一轮在 6、7 两项上明显更严，所以分数不能直接对比。上一轮的 P0 和 P1 这次都没有再出现。

## Design Specificity Verdict

LLM：纹理是自己的，论证是通用的。"策略 → 运行 → 退出码"三联证据是页面的可信度引擎，鳄鱼来自 logo 而不是图库素材。但页面没有说明它要防的风险：agent 会放宽类型、压制诊断、删测试。于是"从不改动代码"读起来像一个属性，而不是解药。"只读"说了三次，一次也没有演示。

Detector：源码扫描 exit 0，但只做了正则匹配；对 .astro 启用 html 引擎的文档配置写法无效，只有数组写法生效，见 B 的报告 §1。URL 扫描 en 桌面 5 条（italic-serif-display ×4、oversized-h1 ×1），zh 移动端 3 条。undersized-ui-text 已全部消失，最小文字为 11.2px。

误报：oversized-h1（CTA 完整位于首屏内）；italic-serif-display（h1 是无衬线正体，只有 em 是衬线；zh 是合成斜体）；只在文件扫描中出现的 extreme-negative-tracking 和 cramped-padding；dist 文件扫描出的 flat-type-hierarchy（base 路径导致 CSS 没有加载）。

## Priority Issues

[P1] 英文 H1 在手机上断成孤字。Hero.astro:17-19 的 `<br>` 叠加自然换行，320px 下 6 行，"gate" 和 "it." 各自单独成行。修复：700px 以下取消强制换行，交给 text-wrap: balance。命令：/impeccable typeset

[P1] 页面 title 仍写 "enforced" / "执行"。index.astro:14、zh/index.astro:14。这与 PRODUCT.md "不得声称 Pluvy 自己阻止 agent"冲突，而且是分享卡片和搜索结果里显示的那一行。命令：/impeccable clarify

[P1] 页面没有说明它要解决的问题。i18n.ts:8 / :57。首屏说明缺一句风险描述：agent 可能通过放宽类型、压制诊断或删除测试，让任务看起来完成了。命令：/impeccable clarify

[P2] 滚动渐显在生产构建里失效。lightningcss 把 animation 和 animation-timeline 合并成 Chromium 不认的简写，整条声明被丢弃，导致开发环境与生产环境行为不一致。global.css:139-143。修复：要么去掉渐显，要么用不会被合并的写法（例如 @supports 块）。命令：/impeccable animate

[P2] 首屏装饰压字，次级链接点击区域偏小。鸟的飞行路径每个周期会穿过标题约 1.5 秒；320px 下鳄鱼位于说明文字下方；.text-link 高 19px。dot-matrix.ts:22-63、global.css:204。命令：/impeccable layout + /impeccable harden

## Persona Red Flags

- 新手："gate" 出现 4 次都没有定义；页面看不出安装成本。
- Riley（怀疑者）：页面上没有许可证和版本；展示的策略不是 examples/ 里那份；同一位置出现两条 architecture.import，像是重复报告；"1 files" 看起来像 bug（这是 CLI 原样输出）。
- Casey（移动端）：英文 H1 断出孤字；320px 下鳄鱼压在说明文字上；策略块横向滚动时没有提示。
- 工程负责人：没有 CI 片段；页面没讲"agent 改了策略会怎样"，而 --staged 遇到策略变更会以 exit 2 拒绝，这是最有说服力的事实；没说明 test.deletion 只在 --base 和 --staged 下运行；没提醒"exit 0 也可能带警告"。

## Minor Observations

- 博客没有中文版，/zh/blog/ 返回 404；语言切换只在落地页提供。
- 没有 og/twitter 元信息，也没有 hreflang。
- 跳转链接的目标 #main-content 没有 tabindex="-1"。
- Capabilities.astro 和 BlogPreview.astro 仍然没有被引用。
- 优点：证据三联、不夸大、类型系统有语义分工。

## Questions to Consider

- 页面能否演示"只读"，而不只是声明，例如展示 agent 修改策略后 --staged 返回 exit 2？
- 鳄鱼要讲什么？如果它不解释门禁，它就是模板纹理。
- 结尾能否用"MIT、无写入路径、一行命令即可移除"做风险兑现，而不是再复述一遍主张？
