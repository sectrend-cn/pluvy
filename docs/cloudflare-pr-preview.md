# Cloudflare PR preview: build enabled, upload blocked

`preview-website.yml` builds PR previews, but its deploy job has an unconditional
`false` guard. This is intentional: the requested `pull_request` event cannot
provide an immutable, trusted workflow when the PR can change its own YAML.
No Cloudflare upload is enabled by this change. Do not remove that guard simply
because credentials become available.

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

The existing `deploy-website.yml` remains byte-identical. It deploys only on
matching pushes to `main` or manual dispatch. Publishing this feature branch
and opening its draft PR cannot trigger it. Existing CI may run engineering
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

Ops can choose a separately configured
[protected GitHub Environment](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
with required reviewers, prevention of self-review and bypass, and credentials
stored only in that environment. A subsequent reviewed change would bind only
the deploy job to that environment and replace the unconditional guard. Reviewers
must inspect the exact run's workflow, every credential-bearing step, pinned
tooling and artifact validation before approving each revision. Removing the
environment declaration must leave credentials unavailable. This is a human
trust boundary; it does not make automatic execution of arbitrary PR YAML safe.
Do not provision repository-level copies of those credentials. No environments,
secrets, approval rules or other repository settings were changed for this work.

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
Ops owns provisioning after selecting a trust boundary. Use the narrowest
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
Validate the workflow with actionlint. Build both root and default bases using
the real locked website dependencies; run the normal repository engineering
checks. These checks do not exercise GitHub runner isolation, protected environment
approval, Cloudflare authorization, live public access or deployed headers.
