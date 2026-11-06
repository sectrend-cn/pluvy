# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: engineering teams that use AI coding agents to write production code. They need an independent check at the end of each agent task, because an agent can make a task look finished by weakening types, suppressing diagnostics, removing tests or crossing architecture boundaries.

The website and docs serve this team first. Individual developers who install and run the tool use the same docs; `docs/getting-started.md` addresses them directly.

## Product Purpose

Pluvy is a read-only engineering policy gate for Python, Go, Java, JavaScript/JSX and TypeScript/TSX. It reads a repository's committed policy, analyzes an exact source snapshot and reports findings with an exit code that a person, agent or CI job can act on.

Success means a team can let agents write code and still trust that its type, test and architecture standards held, without giving the gate permission to change the code.

## Positioning

Pluvy is a guardrail for agent-written code. It stands outside the agent's edit loop: the policy is committed by hand, the gate never changes the code it judges, and a green result cannot come from the gate repairing or negotiating anything.

Read-only is the mechanism that makes this claim credible. A tool that also rewrites code cannot truthfully say the same.

## Operating Context

- Agents run the gate at the end of a code task. The repo ships an Agent Skills directory at `.agents/skills/pluvy/` that any agent able to read files and run shell commands can follow. No specific agent is promised to discover it automatically.
- Developers run `pluvy --all` for a full audit, `pluvy --base <commit>` for changed code and `pluvy --staged` for index blobs.
- CI and containers run the same commands. Pre-commit hooks are possible but must be installed explicitly.
- Each target repository owns and commits `.pluvy/pluvy.json`. Policy changes need their own full audit and architecture review.
- Optional agent review rules invoke a configured ACP agent, which submits findings through registered MCP tools.

## Capabilities and Constraints

- No run mode modifies, stashes, stages, restores, deletes or rewrites source files, and no run mode changes Git configuration. Never describe Pluvy as fixing, repairing or auto-correcting code.
- Pluvy reports; the integration decides whether a task may proceed. Do not claim that Pluvy itself prevents an agent from acting.
- Exit codes: 0 means pass or warnings only, 1 means error findings, 2 means configuration, encoding, filesystem or Git failure.
- Checks cover types, suppressions, test deletion and assertion erosion, architecture and ownership, unused code, control-flow handling, guarded projection and function size. `test.deletion` runs only in `--base` and `--staged` audits.
- Requires Python 3.12 or newer. Install from a source checkout with `uv tool install` or pip, or build the Docker image.
- Terminology: "gate", "policy", "finding", "checker", "full audit". The product name is "Pluvy" in prose and `pluvy` for the command.
- Message order on the public site: the agent guardrail message leads, and read-only follows as the reason the guardrail is credible. The blog still leads with read-only.

## Brand Commitments

- Open source under the MIT License, from Sectrend Information Technology Co., Ltd. The repository is `sectrend-cn/pluvy`.
- English and Simplified Chinese are both required. New public product surfaces ship in both languages.

## Evidence on Hand

- Product documentation: `README.md` and `docs/`.
- Per-checker references: `.agents/skills/pluvy/references/checkers/`.
- Example policy: `examples/.pluvy/pluvy.json`.
- Blog post: `website/src/content/blog/why-pluvy-never-rewrites-your-code.md`.
- Existing artwork: `website/public/images/pluvy-bird.svg`, `website/src/assets/pluvy-natural-neck.svg` and `website/public/animations/crocodile.html`. These are not confirmed as binding brand assets.
- Language coverage today: the landing page has a `/zh` version. Of the docs, only getting-started has a Chinese translation. The site publishes it under `/zh/docs/`; other Chinese doc routes fall back to English with a notice.
- The repository contains no customer names, testimonials or benchmarks. Whether any exist elsewhere is undecided. Do not invent them; ask for real ones.

## Product Principles

1. Independence is the product. The gate stays separate from the agent and the code it judges.
2. Findings are evidence. Developers and reviewers own the response, so Pluvy never edits on their behalf.
3. Policy belongs to the team. It lives in the repository, and changing it to get a green result is not a fix.
4. Claim only what the analysis does. State real limits, scopes and exit codes instead of implying total protection.
5. Both languages are first-class. A Chinese reader gets the same product truth as an English reader.
