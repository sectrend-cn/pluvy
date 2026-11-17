# Pluvy 快速入门

> 本页为译文，英文对照版本见 [../getting-started.md](../getting-started.md)。

本指南面向采用 Pluvy 的开发者，介绍命令行安装、仓库策略配置、日常运行、存量问题处置，
以及在每个人工或 Agent 代码任务结束后运行门禁的工作流。

Pluvy 是只读的语法解析型工程策略门禁：任何运行模式都不修改、暂存、还原、删除或重写源文件，
也不改动 Git 配置。

## 快速上手

在要检查的 Git 仓库根目录执行：

```sh
uv tool install pluvy
mkdir -p .pluvy
echo '{"version": 2, "include": ["src/*", "tests/*"], "checkers": {}}' > .pluvy/pluvy.json
pluvy --all
```

每行输出一条检查结果，最后是汇总。以声明了 `def load(value: Any) -> Any` 的 `src/app.py`
以及调用 `load(1)` 后断言 `True` 的测试为例：

```text
src/app.py:4:17: type.annotation: Preserve a concrete contract instead of Any
src/app.py:4:17: type.broad: Do not erase contracts with typing.Any
src/app.py:4:25: type.annotation: Preserve a concrete contract instead of Any
src/app.py:4:25: type.broad: Do not erase contracts with typing.Any
tests/test_app.py:5:5: warning: unused.return: Return value from 'load' is discarded
tests/test_app.py:6:5: test.tautology: Assertion in test_load cannot fail because it restates the same expression or a literal true. Assert an independently produced value or outcome instead.
Diagnostic scope: full_files.
Usage reference scope: 2 files.
Architecture all: 2 files; 6 findings.
```

每条结果的格式为 `path:line:column: rule: message`；规则名前带 `warning:` 的是警告，
不改变退出码。Python 的 `typing.Any` 会同时触发 `type.annotation` 与 `type.broad`，
所以每个位置出现两次。末行给出运行模式、审计文件数与结果总数。本例存在错误级结果，
退出码为 `1`；在存量代码库上这是正常的首次基线结果，见
[存量仓库的首次全量审计](#存量仓库的首次全量审计)。

如果源码不在 `src/` 与 `tests/` 下，请调整 `include`：未命中任何受支持源文件时，`--all`
返回退出码 `2`。审阅首次结果后提交 `.pluvy/pluvy.json`，后续改动对照基准提交做增量门禁，
例如 `pluvy --base origin/main`。下面各节展开说明。

## 安装

### 前置条件

- Python 3.12 或更高版本。
- 建议使用 `uv` 管理独立的工具环境，安装方式见
  [uv 安装指南](https://docs.astral.sh/uv/getting-started/installation/)。

### 从 PyPI 安装

从 [PyPI](https://pypi.org/project/pluvy/) 安装命令行工具：

```sh
uv tool install pluvy
```

不使用 `uv` 时，可用 `pip` 安装：

```sh
python -m pip install pluvy
```

只想单次试跑而不安装时，运行 `uvx pluvy --all`。

`uv tool install` 将 `pluvy` 放入 `uv` 可执行目录（`uv tool dir --bin` 可查看，
通常为 `~/.local/bin`）；不在 `PATH` 中时运行 `uv tool update-shell`。
`pip` 将 `pluvy` 安装到当前 Python 环境的 scripts 目录。覆盖已有的同名 `uv` 工具时，
执行 `uv tool install --force pluvy`。

### 获取源码

PyPI 包仅含命令行工具。`examples/` 样例策略与 `.agents/skills/pluvy/` 技能目录位于
[GitHub 仓库](https://github.com/sectrend-cn/pluvy)，按需克隆即可。下文以
`/path/to/pluvy` 指代检出目录；安装未发布的源码改动时，将安装命令中的 `pluvy`
换为 `/path/to/pluvy`。

### 验证

```sh
pluvy --help
pluvy --root /path/to/project --all
```

第一条确认命令可用，并列出支持的全部选项：`--root`（默认 `.`）、`--config`
（默认 `.pluvy/pluvy.json`）、`--format`（`text` 或 `json`），以及必选且互斥的
`--all` / `--staged` / `--base`。第二条对目标仓库执行全量审计；若目标仓库尚未按
[配置](#配置) 建立策略文件，命令会以退出码 `2` 报告找不到策略，属预期行为，完成配置后再验证即可。

### skill 获取

Agent 使用的技能目录来自仓库检出：将 `.agents/skills/pluvy/` 复制到目标项目的技能目录即可，
接入方式见 [Agent 接入](#agent-接入)。

## 配置

### 建立仓库策略

每个目标仓库维护并提交自己的 `.pluvy/pluvy.json`（在所有模式下均相对 `--root` 解析）。
Pluvy 不提供自动生成策略文件的子命令，需手动编写并提交；CLI 仅定义 `--all`、`--staged`、
`--base`、`--root`、`--config`、`--format` 及 `-h, --help`。

起步有两种方式：将 [样例策略](../../examples/.pluvy/pluvy.json) 复制到目标仓库的
`.pluvy/pluvy.json` 并按目录结构调整；或直接编写一份最小可用策略（当 `checkers` 为空对象或省略时，
全部 22 个检查器默认启用）：

```json
{"version": 2, "include": ["src/*", "tests/*"], "exclude": [], "checkers": {}}
```

可按需补充的常用配置项：

- `include` / `exclude`：圈定参与全部检查的文件；大小写敏感，`*` 可跨 `/`，路径相对仓库根目录。
- `architecture.owner` 下的 `owners`：为每个选中文件声明唯一的责任归属。
- `architecture.import` 下的 `boundaries`：声明禁止的跨层依赖方向。
- `function_size`：函数行数、语句数、复杂度、嵌套层数与参数个数上限。

从最小策略起步时，建议按以下顺序逐步建立，每步先跑一次检查再决定下一步：

1. 用 `include` / `exclude` 圈定参与审计的文件范围；
2. 首次运行 `pluvy --all` 获取基线结果——存量仓库通常返回退出码 `1`，属正常现象，见
   [存量仓库的首次全量审计](#存量仓库的首次全量审计)；若范围内没有任何受支持源文件，则返回退出码
   `2`，需先修正 `include`；
3. 在 `architecture.owner` 下补充 `owners`；
4. 在 `architecture.import` 下声明 `boundaries`；
5. 按仓库实际情况调整 `function_size` 阈值，或在 `type.broad` 下补充 `encoding` 声明。

阈值、排除项以及归属与边界调整均属于策略变更，需遵循下一节的全量审计与评审纪律，不能用来掩盖既有违规。

### 变更策略的纪律

策略变更（调整阈值、增加排除项、修改归属或依赖边界、开关检查器）是架构决策，不是消除告警的捷径。
初始版本与每次修订都必须在提交前单独运行 `pluvy --all` 并完成人工评审。当暂存区（index）中存在
策略文件改动时，`--staged` 会以退出码 `2` 直接拒绝执行，避免用未经评审的新策略检查暂存代码。
由于工具不会记录是否跑过全量审计，策略一旦提交，`--staged` 即会采纳；若仓库配置了运行
`pluvy --staged` 的 pre-commit 钩子，请将评审通过的策略变更单独提交，并仅对该次提交跳过钩子
（例如 `git commit --no-verify`）。

完整选项、策略结构、各语言覆盖范围与实现边界见
[检查器配置](../checker-configuration.md)。

## 运行

每次运行必须且只能指定三种模式之一（`--all`、`--staged`、`--base <commit>` 互斥）：

- `--all`：审计策略选中的全部工作树文件（**包含**被 Git 忽略的文件），暴露所有存量技术债。
- `--base <commit>`：对比指定提交与当前工作树（**包含**未跟踪的新文件，新文件做全量检查）。
- `--staged`：只读取 Git 暂存区（index）中的文件内容与策略，不读取未暂存的工作树改动。

常用命令：

```sh
pluvy --all
pluvy --staged
pluvy --base <commit>
pluvy --root /path/to/project --all
pluvy --all --format json
```

`--root` 默认当前目录（Git 模式下必须为仓库根目录），`--config` 默认 `.pluvy/pluvy.json`；
可组合为 `pluvy --root /path/to/project --config .pluvy/pluvy.json --all`。

退出码说明：

| 退出码 | 含义 |
|---|---|
| `0` | 无错误级结果（警告不改变退出码） |
| `1` | 至少存在一条错误级结果 |
| `2` | 配置、编码、文件系统或 Git 失败（含暂存区包含策略变更时的 `--staged`） |

增量模式（`--base` / `--staged`）会完整解析源码快照以建立引用索引，但只报告**受影响的定义与模块级语句**：
修改函数内部会扩展到整个函数（含装饰器与签名），修改类头会选中整个类，修改模块语句会选中该语句，
纯删除保留邻近行锚点，未跟踪新文件做全量检查。文件归属与目录放置规则仍对每个变更文件生效。
报告通过 `scope` 区分 `full_files` 与 `affected_definitions_and_statements`。

其他运行行为：空的全量审计视为配置错误（退出码 `2`）；空的增量审计报告 `0` 个文件；语法错误仅在
`stderr` 输出警告而不改变退出码，后续检查在恢复后的语法树上尽力继续，结果可能受限。

`--format json` 输出当前报告结构：`scope`、`findings`（每项含 `severity`）、`usage_files`、
`disabled_checkers` 以及模式与文件计数。该 JSON 结构随实现演进，未承诺作为跨版本不变的外部协议，
升级时请以实际输出为准。

### 排错

| 输出 | 原因 | 处理方式 |
|---|---|---|
| `Architecture gate error: [Errno 2] No such file or directory: '.../.pluvy/pluvy.json'` | `--root` 下缺少策略文件，或在子目录运行 | 添加策略文件，回到仓库根目录运行，或显式传 `--root` |
| `Architecture gate error: fatal: Needed a single revision` | `--base` 指定的提交不存在（如首次提交前传 `--base HEAD`） | 先完成首次提交，或改用 `--all` |
| `Architecture gate error: Policy changed in index; review it and run --all before adoption` | 暂存区含有策略文件改动时运行了 `--staged` | 按 [变更策略的纪律](#变更策略的纪律) 单独评审并提交策略 |
| `Architecture base: 0 files; 0 findings.` 且退出码 `0` | 与基准无差异（例如任务改动已提交后仍运行 `--base HEAD`） | 不能视为通过：改用本次任务首个提交的父提交作为 `--base` 重跑 |

## 告警处置

### 三条处置路径

1. **优先修复代码**：检查结果是策略违规的证据，默认处理方式是修改代码恢复契约。
2. **经审批的逐行抑制（全部受支持语言）**：Python、Go、Java 与 JavaScript/TypeScript 家族均允许在违规行的上一行使用单行注释抑制一个精确的诊断 ID（Python 用 `#`，Go、Java 与 JS/TS 家族用 `//`）。该机制仅限**事先获得人工明确批准的例外**——批准先于理由存在，注释中的理由只用于记录该批准而非证明安全，代码用途变化时须重新审视。块注释、通配符、多规则列表或缺失理由均会触发 `type.suppression` 错误。完整语法与规则见 [逐行诊断抑制](../comment-suppressions.md)。
3. **修订策略**：调整阈值、排除项或归属属于架构决策，必须单独运行 `--all` 全量审计并人工评审，严禁靠放宽策略把门禁刷绿。

### 债务语义

`--all` 暴露全部存量债务，`--base` 仅报告本次改动触及的定义与语句，两者不可互相替代：

- `0`：本次检查范围内无错误级结果（可含警告）。
- `1`：本次检查范围内存在错误级结果，需逐项处理。
- `2`：门禁因配置、编码、文件系统或 Git 错误无法完成检查；先修复配置或环境问题，再重新运行门禁。

### 存量仓库的首次全量审计

存量代码库建立初始策略后，首次运行 `pluvy --all` 通常返回退出码 `1`，这是正常的基线摸底而非工具故障：

1. 逐条审阅检查结果，优先修复真实的契约或测试违规。
2. 对确属历史债务、或默认阈值与仓库形态不符的项，有依据地调整策略（阈值、排除项、归属），再重跑 `--all` 并评审。
3. 记录已修复项、通过策略调整接纳的项以及评审结论。

## 按任务门禁

在每个代码任务结束、汇报完成前运行一次门禁，并如实报告运行模式、退出码、错误与警告计数及关键问题；人工开发与 Agent 执行遵循同一标准。不同场景对应的命令选择（未提交改动、任务已产生提交、起始提交未知、`--staged` 边界）、三条约束规则、运行后自检及报告格式以 [pluvy skill](../../.agents/skills/pluvy/SKILL.md) 为准。其中特别注意文件数自检：报告末行形如 `Architecture base: N files; M findings.`，当任务确实改动了代码而 `N=0` 时属于基准选错的假通过，必须重选基准重跑。

## Agent 接入

技能目录位于仓库检出的 `.agents/skills/pluvy/`（包含 `SKILL.md` 与 `references/`），支持三种接入路径：

1. **原生 skills 目录**：若目标项目或 Agent 遵循通用 skills 目录约定，将 `.agents/skills/pluvy/` 复制到项目级或用户级 skills 目录，Agent 即可按描述自动加载。
2. **Agent 专属目录适配**：若 Agent 仅从自身专属目录读取指令，按目标目录所在位置选择接入方式：
   - **仓库根目录（`--root`）内部**：必须**复制**目录，严禁在 `--root` 内创建目录软链接——`--all` 与 `--base` 在 `include`/`exclude` 过滤前就会拒绝遍历仓库内的任何目录软链接并返回退出码 `2`（`exclude` 无法绕过）。上游更新后重新复制同步即可。
   - **仓库根目录外部**（例如用户主目录下的全局 skills 目录）：可使用软链接保持单一事实来源。
3. **AGENTS.md 指针片段**：对从 `AGENTS.md` 读取指令的 Agent，手动将以下片段粘贴到该文件中（不要用脚本自动改写用户的 `AGENTS.md`）：

```markdown
<!-- pluvy skill pointer -->
When adopting, configuring, or running pluvy, or triaging its findings,
first read `.agents/skills/pluvy/SKILL.md` and follow it.
```

完整接入方式与边界说明见
[Agent 接入说明](../../.agents/skills/pluvy/references/agent-integration.md)。
