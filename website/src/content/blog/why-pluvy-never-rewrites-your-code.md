---
title: Why Pluvy Never Rewrites Your Code
description: Read-only analysis keeps the policy gate independent from the changes it reports.
pubDate: 2026-11-05
authors: [Pluvy team]
tags: [engineering, read-only]
draft: false
---

Pluvy has a deliberately narrow contract: examine an exact source snapshot, apply the repository's engineering policy, and report what the analysis found. It does not repair the source, stage a change, restore a file, or rewrite Git configuration.

That constraint is not a missing convenience feature. It defines who owns a code change.

## Findings are evidence, not edits

A policy finding identifies a location and a rule. The appropriate response still depends on the code's domain contract, its callers, and the owning team's intent. A mechanical rewrite cannot establish those facts.

This matters most for architecture and type boundaries. Removing a broad type, moving a module, or changing a dependency can alter behavior far beyond the reported line. Pluvy leaves that decision with the developer and the review process.

## The snapshot stays intact

Every run mode preserves the same read-only boundary:

```sh
pluvy --all
pluvy --base <commit>
pluvy --staged
```

A full audit exposes the debt in the selected working files. A base run compares a commit with the working tree and reports affected definitions and statements. A staged run reads blobs from the index rather than silently substituting unstaged content.

These modes answer different questions, but none of them changes the evidence being examined.

## Policy changes need their own review

A threshold, exclusion, ownership declaration, or dependency boundary is part of the repository's architecture. Changing it to obtain a green result is not the same as fixing a finding.

The policy therefore lives with the project at `.pluvy/pluvy.json` and is committed by hand. Revisions require a separate full audit and review. The gate reports the policy; it does not quietly negotiate with it.

## Automation can still be responsible

Read-only does not mean disconnected. Pluvy fits local development, CI, pre-commit hooks, JSON-consuming tooling, and coding agents that run the gate after each task. The integration can decide how to present findings and whether a task may proceed.

What it should not do is confuse a successful gate with permission to modify the repository. Pluvy supplies evidence. Developers and reviewers own the response.
