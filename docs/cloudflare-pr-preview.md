# Cloudflare PR preview: build enabled, upload blocked

`preview-website.yml` builds PR previews, but its deploy job has an unconditional
`false` guard. This is intentional: the requested `pull_request` event cannot
provide an immutable, trusted workflow when the PR can change its own YAML.
No Cloudflare upload is enabled by this change. Do not remove that guard simply
because credentials become available or Plan A has been selected. The deploy
job alone is prepared to reference the fixed Environment `cloudflare-pr-preview`;
the build job references neither that Environment nor Cloudflare secrets.

## Verified repository inputs and production effects

The Astro configuration uses `output: 'static'` and reads `ASTRO_BASE`, defaulting
to `/pluvy`. `website/package.json` runs `scripts/sync-docs.mjs` as `prebuild`;
that script reads Markdown from both `docs/` and `docs/zh/`. Both `website/**`
and `docs/**` therefore trigger the preview on PR `opened`, `synchronize` and
`reopened` events. No other event is enabled. A workflow-only change does not
trigger it unless the PR also changes one of those input paths.

The build uses Node 22, `npm ci`, `npm run build`, and `website/dist`, with
`ASTRO_BASE=/` shared by Astro and documentation link rewriting. The default
documentation base remains `/pluvy`; trailing slashes are normalized to avoid
double slashes at the root.

`BaseLayout.astro` reuses the existing `basePath()` contract for the favicon.
The rendered URL is `/favicon.svg` for the root preview and
`/pluvy/favicon.svg` for the default GitHub Pages base. A root base must never
emit `//favicon.svg`, which a browser interprets as another host.

The existing `deploy-website.yml` remains byte-identical. It deploys only on
matching pushes to `main` or manual dispatch. Publishing this feature branch
and opening or updating this PR cannot trigger it. Existing CI may run engineering
checks on the branch push and PR. Release publication requires a version tag.
A future merge into `main` would trigger the existing website deploy because
this change touches website and documentation inputs; merging is outside this task.

## Trust boundary and activation decision

[GitHub's PR event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request)
uses the PR merge ref, including workflow changes from the PR head. A contributor
able to change that YAML can remove guards, add secret references to the build,
or replace inline deployment commands. Two jobs, a same-repository check, path
filters, pinned actions and a workflow-diff check in that same mutable YAML do
not solve this. Repository or organization secrets exposed to PR workflows
cannot safely hold the preview token under this threat model.

Plan A selects a manually approved protected Environment. Its YAML binding is
prepared, but the unconditional guard stays in place until Ops confirms the
configuration and a later, separately reviewed commit is approved to lift it.
An absent or unprotected Environment, early repository-level credentials, or
the Plan A decision alone cannot enable this reviewed workflow's deploy job.
Removing the Environment declaration in a future workflow must leave credentials
unavailable. This is a human trust boundary; it does not make arbitrary PR YAML
trusted. No Environments, secrets, approval rules or other repository settings
were created or edited by the coding agent.

## Plan A Ops checklist (洛托姆)

1. Configure the exact Environment **`cloudflare-pr-preview`**. Read-only
   inspection found only `github-pages` and `pypi` in the repository; the chosen
   name collides with neither existing Environment nor a production workflow
   binding. Do not reuse either existing Environment. Keep the upload guard
   unchanged throughout setup; the skipped job does not exercise Environment
   protections. Do not run a credential-bearing job to test configuration.
2. Configure **at least two distinct qualified people** in the required-reviewer
   pool, individually or through a team with at least two qualified members.
   Each must have at least read access and be able to review Actions security.
   GitHub permits up to six user/team entries and requires **one eligible
   approval per deployment job**, not approval from everyone listed or a
   two-person approval quorum. A configured reviewer who did not initiate the
   run must manually approve each deploy run. If two independent approvals are
   desired, the built-in reviewer list does not enforce that extra requirement.
3. Set **Prevent self-review: ON**. GitHub excludes the deployment/run initiator
   from approving. For this preview policy, the approver must also be independent
   of the PR author. PR #23's author is **`sunny0826`**. If `sunny0826` is the only
   available reviewer, setup is **blocked**: 洛托姆 must ask the user to designate
   another qualified reviewer. That person's identity and access remain
   unconfirmed. Do not disable self-review prevention or change the rerun actor
   as a workaround for author self-approval.
4. Set **Prevent administrators from bypassing protection rules: ON**. In
   GitHub's UI this means **Allow administrators to bypass configured protection
   rules: OFF**. Do not use an admin bypass to release a waiting job.
5. Set **Deployment branches and tags: Selected branches and tags**. Add exactly
   one **Branch** rule with pattern **`refs/pull/*/merge`** and no Tag rules.
   Do not add `main`, `cloudflare-pr-preview`, additional rules or a
   no-restriction policy. GitHub's
   [deployment-branch documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments#deployment-branches-and-tags)
   matches rules against `GITHUB_REF` and explicitly documents this PR pattern.
   For `pull_request`, that ref is `refs/pull/N/merge`, not the head branch name
   or `main`. A main-only or protected-branches-only policy would not correctly
   admit these PR merge refs. This selected Branch rule excludes production
   `main` refs and tags. It is separate from the explicit Cloudflare Pages branch
   `pr-N`; it does not enable fork uploads or any additional workflow events.
6. Store **only** `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in this
   Environment. Never provision copies as repository secrets or broadly
   inherited organization secrets. Keep the build job outside the Environment.
   Credential values are not needed in this document, PR review or agent chat.
7. For **every exact run/revision**, before approving its Environment gate,
   inspect the workflow YAML actually used by that run from its PR merge/head
   tree using GitHub's workflow-file view for that run. Record the run URL/ID
   and attempt, immutable workflow/merge commit SHA and PR head SHA; inspect
   `.github/workflows/preview-website.yml` at that workflow revision, not the
   current branch tip or default branch. Do not assume an API's `head_sha` is
   the merge commit or resolve a moving merge ref after a new PR update.
   Check every secret reference, checkout, action pin, inline command, artifact
   validator and upload target.
   A general PR approval or approval of an earlier run is insufficient. New
   commits and reruns require another review of their exact revision and gate.
8. Confirm all controls and reviewer eligibility are available and configured,
   and verify the Cloudflare metadata listed below. Report completion to the
   user without exposing secret values. **Activation is a future, separately
   reviewed commit** that lifts the unconditional `false` guard while retaining
   the fixed Environment gate and same-repository restriction. This change does
   not lift it. Until that future approval, even a fully configured Environment
   must result in a skipped deploy job.

### Plan and visibility availability

The repository was reconfirmed **public** through read-only GitHub repository
metadata. GitHub's
[Environment setup documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments#who-can-use-this-feature)
and [deployment review documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments#who-can-use-this-feature)
state that current GitHub plans support Environments, Environment secrets and
protection rules for public repositories; legacy Bronze/Silver/Gold plans do
not. Required reviewers on Free/Pro/Team are limited to public repositories.
Changing visibility to private/internal would require a new capability audit:
having an Environment on a paid plan alone does not establish that required
reviewers and every other protection are supported. Read-only organization
metadata did not disclose its plan; the actual plan and new Environment's
controls have not been verified. Ops must confirm every checklist control,
including self-review prevention and no administrator
bypass. If any is unavailable, report a **blocker** and leave uploads disabled;
do not weaken the controls to fit the plan or visibility.

If fully automatic secret-safe previews are required even for workflow-changing
PRs, an independently enforced trusted execution boundary is still needed.
The forbidden alternative workflow events are not used as a workaround.

## Prepared upload design

- Only the hardcoded project `pluvy-preview` is passed to Wrangler. The branch is
  explicitly `pr-<positive PR number>`, validated as decimal digits. No command
  can default to the production branch in this reviewed implementation.
- The build job has read-only repository access, no credential persistence and
  no Cloudflare secret references. The deploy job has no GitHub token permissions,
  no checkout and no PR scripts or tools. Cloudflare credentials appear only in
  the final upload step, after artifact validation and tool installation.
- Fork PRs can build without Cloudflare secrets. All uploads currently skip,
  including forks. The prepared deploy condition also excludes forks; its upload
  step exits successfully when either required credential is absent, without
  invoking Wrangler or attempting interactive authentication.
- Actions are pinned to full commit SHAs. Neither job restores or saves Actions
  caches. The tar artifact has a run/attempt-specific name, a short retention
  period and an immutable artifact ID passed to the dependent job. Download uses
  that ID in the same run, with no cross-run or name-based fallback. Compromised
  builds can still poison their own artifact and outputs; identity and digest
  checks do not establish that its contents are safe or correct.
- A pinned download action unwraps the artifact container into a fresh incoming
  directory. The inner tar is never extracted with `extract` or `extractall`.
  The inline validator copies regular file bytes with exclusive creation into a
  separate fresh upload directory. It rejects traversal, absolute/empty/dot
  components, backslashes, control characters, characters outside its filename
  allowlist, links, devices,
  FIFOs, duplicate/case-colliding paths and oversized archives/members/counts.
- Paths beginning with `.` or `_` are rejected in every component except
  `_astro`. This excludes `_worker.js` files and directories, `_routes.json`,
  `_headers`, `_redirects` and other special underscore inputs. `functions`,
  `node_modules`, package manifests and Wrangler configs are also forbidden.
  Unsafe content rejects the upload rather than silently altering the site.
  The real Astro build also emits an empty root `.nojekyll` marker; the validator
  omits that inert GitHub Pages marker. Nonempty, nested or linked variants fail.
- Wrangler `4.160.1` is installed in an empty tooling directory using an isolated
  environment, empty npm configs, a fresh cache and `--ignore-scripts`. It runs
  from a different empty directory, outside the artifact and PR tree. The final
  process receives an explicit environment allowlist. npm, Node, Wrangler,
  their dependency supply chain, pinned actions and hosted runners remain
  trusted dependencies; pinning Wrangler does not lock all transitive versions.

[Cloudflare Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
can compile a working-directory `functions/` tree or a site's `_worker.js`.
The isolated working directory and validation rules prevent either input from
reaching this upload. Browser JavaScript remains ordinary public static content.

## Public access, indexing and external verification

After validation, the trusted deploy code creates the only accepted `_headers`:

```text
/*
  X-Robots-Tag: noindex, nofollow, noarchive
```

This uses the documented [Pages header mechanism](https://developers.cloudflare.com/pages/configuration/headers/).
It applies to static responses, including non-HTML assets. PR-provided headers
and redirects cannot remove or bypass it. No authentication or Cloudflare Access
restriction is introduced. `noindex` is a crawler directive, not access control;
the public site can still be copied by visitors.

Authenticated Cloudflare project metadata was not available through an authorized
read tool. The reported existence and DirectUpload type of `pluvy-preview`, its
`main` production branch, absence of Git sources/custom domains/deployments, and
public preview access remain unverified. Ops must verify those facts through
their existing authorized access before any activation. This change does not
create or alter a Cloudflare project. No deployment or live HTTP header test was
performed; after an approved future preview, verify public access and
`X-Robots-Tag` on both the deployment URL and branch alias, including docs and 404s.

Required future secret names are `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`, matching
[Wrangler's environment variables](https://developers.cloudflare.com/workers/wrangler/system-environment-variables/).
Ops owns provisioning after confirming the Plan A controls. Use the narrowest
available Pages upload permissions and account scope. Account-scoped Pages Edit
access must not be assumed to isolate one project; a stolen token may affect
other projects. The hardcoded target constrains this code, not a stolen credential.
No credential values are needed for review or local tests.

## Local verification

Run the artifact tests with `python3 -m unittest discover -s .github/tests -v`.
They execute the workflow's actual inline validator on static files, malicious
paths, executable Pages inputs, symlinks/hardlinks/special files, duplicates,
missing indexes and oversized members, and exercise missing-credential skipping.
Run `node --test website/tests/sync-docs.test.mjs` with Node 22 for default,
root, explicit GitHub Pages and nested/trailing-slash documentation link cases.
Run `node --test website/tests/base-layout.test.mjs` after dependency installation
and documentation sync to build the real site in temporary output directories.
It checks rendered favicon URLs and same-origin resolution on landing, Chinese,
blog and 404 pages for root, default, nested and trailing-slash bases. The
token-less preview build runs this matrix before packaging its original output;
the matrix does not modify the preview artifact directory.
Validate the workflow with actionlint. Build both root and default bases using
the real locked website dependencies; run the normal repository engineering
checks. These checks do not exercise GitHub runner isolation, protected environment
approval, Cloudflare authorization, live public access or deployed headers.
