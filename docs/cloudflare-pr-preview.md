# Cloudflare PR previews: Plan B trusted automatic publishing

Plan B separates the token-less PR build from a trusted default-branch
`workflow_run` publisher. There is no per-run human approval and no unconditional
upload guard. Admission failures are errors, including missing credentials.
**Publishing is not active in this PR.** The publisher must first exist on `main`,
and Ops must configure the Environment. Admission has a positive path under the
PR-head policy below. This PR must not be merged by the agent.

## Build and trust boundary

`.github/workflows/preview-website.yml` is named `Cloudflare PR preview`. Its only
trigger is `pull_request` with `opened`, `synchronize`, and `reopened`. Changes to
**only `website/**` and `docs/**`** trigger the build. A workflow-only or tests-only
change does not trigger it. Workflow permissions are empty; the build alone has
`contents: read`. It requests no Environment and references no secrets. The
previous in-workflow deploy job has been removed entirely.

The build explicitly checks out `${{ github.event.pull_request.head.sha }}` with
`persist-credentials: false`. The preview is the **PR branch head tree**, not the
merge tree with `main`. The immutable head selection is intentional; checkout
must not omit `ref` or select `refs/pull/*/merge`. The build uses Node 22 without
shared caches, runs `npm ci` and `npm run build`, and retains
`ASTRO_BASE=/`. Root favicon URLs must be `/favicon.svg`, never `//favicon.svg`;
the default production base remains `/pluvy`. The build packages `website/dist`
as an uncompressed tar without following links. The artifact is named exactly
`website-preview-<run_id>-<run_attempt>` and retained for three days.

`.github/workflows/preview-website-publish.yml` listens for completed runs of that
workflow name. GitHub executes `workflow_run` workflows only when their file
exists on the default branch, with the default-branch commit as `github.sha`.
Both trusted jobs check out only that SHA and disable credential persistence.
No PR checkout, PR script, or artifact code executes in the publisher.
[GitHub documents this event boundary and its risks.](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)

The name filter is necessary but insufficient: a contributor can add a sibling
workflow with the same name. Admission additionally binds the exact registered
path `.github/workflows/preview-website.yml` and workflow ID **415667994**, verified
through GitHub's API during implementation. A contributor can still edit the
build YAML at that same path and retain that ID. Its artifact is always
untrusted. The content boundary is static validation and never executing PR or
artifact code, not trusting how the build produced the artifact. Anyone who can
push `main` can change the publisher and its trusted module.

Path filters remain PR-controlled, backed by a trusted eligibility gate on every
`admit()` call. The complete paginated GitHub Files API list must match a
non-negative `changed_files` snapshot capped at 3000. The PR number, head SHA,
base SHA, and file count must remain identical before and after listing. At
least one current or previous filename must be a real, case-sensitive website
or docs input, including renames into or away from those trees. Truncation,
malformed responses, and API errors fail closed. Artifact manifests, workflow
outputs, and PR-supplied lists provide no eligibility evidence. Static validation
and never executing PR or artifact code remain the content boundary for bytes.

## Admission, currentness, and serialization

`.github/scripts/preview_publish.py` owns the testable, fail-closed policy and
shared static validator. It runs with `python3 -I`, uses only `GITHUB_TOKEN` for
GitHub API reads, constructs endpoints under the fixed repository, and narrows
responses into concrete contracts. It never reads facts from an artifact
manifest, workflow outputs, PR-provided URLs, or `workflow_run.pull_requests`.

Admission requires all of the following:

1. The event repository, source run repository and owner, and head repository are
   exactly `sectrend-cn/pluvy` / `sectrend-cn`. The trusted runner repository must
   match too. The workflow path and ID must match both payload and live API.
2. The source event is `pull_request`, status is `completed`, and conclusion is
   `success`. The payload run ID equals the triggering run ID supplied by the
   trusted workflow. Live run and exact-attempt identities must agree with that
   run and its payload attempt; a newer rerun invalidates the earlier event.
3. The commit-to-PR API resolves the source `head_sha`. Exactly one current open,
   unmerged PR may match. Its live head SHA must equal the source head SHA. Both
   PR repositories must be this repository, excluding forks, and its base must
   be `main`. Empty, duplicate, ambiguous, or truncated associations reject.
4. Trusted file eligibility uses only the verified PR's
   [GitHub Files API](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files).
   PR snapshots require `base.sha` and a non-negative integer `changed_files`;
   counts above the API's 3000-file cap reject before any file-list request.
   Numbered requests start at page 1 with `per_page=100`, never following Link
   or JSON URLs. Every full page requires another request, including an empty
   final page for exact multiples of 100. The complete collected count must
   equal the snapshot; short/truncated, malformed, oversized, duplicate, missing,
   or failed pages reject. After listing, the same PR is re-fetched: number,
   head SHA, base SHA, and count must be identical, its head must still match the
   run, and it must remain authorized and open. `filename` or optional
   `previous_filename` must be exactly `website`/`docs` or start with their
   case-sensitive `/` boundary. Renames in either direction count; lookalike
   prefixes, dot/traversal segments, leading slashes, and backslashes do not.
   YAML-only/tests-only lists reject. Every invocation of `admit()` enforces
   this policy, including after queuing and immediately before upload.
5. The live run and exact-attempt API must both report that same PR head SHA.
   This is the commit requested by the reviewed checkout configuration, never a
   historical merge SHA. Separately, the PR must currently be mergeable, and
   `refs/pull/<verified-number>/merge` must exist and point to a commit whose two
   parents are current `main` followed by the current verified PR head. Missing
   refs, unknown/conflicted mergeability, stale parents, and mismatched commit
   identities reject. This proves only a current merge relationship, not the
   tree or provenance of the artifact bytes.
6. The triggering run has exactly one unexpired artifact with name
   `website-preview-<payload-run-id>-<payload-attempt>`. An unexpected name,
   additional artifact, missing artifact, wrong run association, or API failure
   rejects. The trusted download uses that immutable artifact ID and exactly
   `github.event.workflow_run.id`, under `runner.temp`.

The first job performs admission without the Cloudflare Environment. The single
publish job depends on those verified outputs, uses `cloudflare-pr-preview`, and
sets concurrency to the verified PR number. Two jobs are intentional: GitHub
cannot derive a job's concurrency from an earlier step of that same job. The
publish job repeats admission after obtaining its concurrency slot and again
immediately before upload. The verified PR and artifact ID must remain unchanged.
Concurrent publish jobs for a PR serialize; no PR-supplied number sets the group.
Both jobs have timeouts and only `contents: read`, `actions: read`, and
`pull-requests: read`. No PR comments or write permissions are required.

### Head-tree previews and current merge relationships

Read-only inspection of successful build run **43178959208**, attempt **1**, found
that the run API, exact-attempt API, job API, and check suite all report the PR head
`5af77ed1cf114ce2277ddb684fac7ff7db711069`. The live PR merge ref instead resolves to
`69c39f0a757a1b0b73222a9b21f315b22c34171b`. The run's `head_commit.id` also reports
the PR head. Those responses do **not** prove the checkout's merge SHA.
The [Actions run API](https://docs.github.com/en/rest/actions/workflow-runs)
provides run/attempt queries, but its head SHA must not be assumed to mean the
`pull_request` event's checkout SHA.

The build therefore requests the immutable **head**, and admission requires
`workflow_run.head_sha == live run.head_sha == attempt.head_sha == live PR.head.sha`.
A force-push or new PR commit invalidates an earlier build. Historical merge
checkout evidence is neither available nor required under this policy. Nothing
from artifact manifests, job logs, or untrusted workflow outputs supplies SHA
evidence. The current merge ref is resolved independently through the Git ref and
Git commit APIs, including its two parents; a run head SHA never becomes a merge
SHA by relabeling it.

If `main` moves after the build, the preview still reflects the **head tree from
the successful run**, not a new merge with the updated base. A new `synchronize`
is required to rebuild; moving `main` alone does not trigger this PR build. While
the server merge ref still has the old base parent, admission rejects it. Once
GitHub regenerates a valid current relationship, admission may accept the same
current head artifact, explicitly retaining its head-tree identity. It never
claims that artifact is the new merge tree. Tests retain the stale-base negative
and separately prove that a regenerated merge cannot relabel the artifact.

The artifact remains untrusted even when these identity checks pass: a PR can
change the build YAML at the same registered path and ID. Static validation and
never executing PR or artifact code remain the content boundary. Admission uses
the available head-currentness evidence; automatic upload requires a future merge
of the trusted publisher to `main` and completed Ops setup. No live publishing
from this PR is claimed.

## Static files and trusted tooling

The shared validator never calls tar extraction APIs. It copies only regular-file
bytes using exclusive creation into a fresh directory, discarding archive modes
and ownership. It rejects traversal, absolute/empty/dot components, non-allowlisted
names, links, sparse/special files, duplicates and case collisions, oversized
archives, oversized members, excess aggregate content and excess entry counts.
An `index.html` is required. Existing destinations and extra outer artifact files
reject. Only an empty root `.nojekyll` marker is omitted.

Dot-prefixed components and underscore-prefixed components other than `_astro`
are forbidden, including `_worker.js`, `_routes.json`, `_headers`, `_redirects`,
and their directory variants. `functions`, `node_modules`, package manifests,
lockfiles, and Wrangler configuration are forbidden at every depth. These rules
prevent Pages execution/configuration inputs from reaching
[Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/).
Ordinary static HTML and browser JavaScript remain untrusted public content.

The validator generates the only accepted `_headers` file:

```text
/*
  X-Robots-Tag: noindex, nofollow, noarchive
```

This follows [Pages' static header mechanism](https://developers.cloudflare.com/pages/configuration/headers/).
`noindex` is a crawler directive, not access control. Public preview XSS is an
inherent residual risk: PR content can execute JavaScript in visitors' browsers.
No authentication or Cloudflare Access protection is introduced.

After validation, trusted code installs exactly `wrangler@4.160.1` with
`--ignore-scripts` into an empty temporary tooling directory. npm runs under
`env -i` with an explicit PATH, isolated empty npmrc files and a fresh cache;
no Cloudflare credentials are present during installation. The final process
runs from a separate empty directory with an explicit environment allowlist.
Only the final upload step references the two Cloudflare Environment secrets;
missing either one fails. The project is hardcoded to `pluvy-preview`, and the
branch is exactly `pr-<verified-positive-integer>`. It cannot default to `main`.
Pinned actions, hosted runners, Node, npm, Wrangler, and their dependency supply
chains remain trusted. Pinning Wrangler does not lock every transitive version.
A narrowly scoped token is still necessary: hardcoding this command's project
does not constrain what a stolen account token could do elsewhere.

## Ops checklist (洛托姆; do not perform from this PR)

1. Create/use the exact Environment **`cloudflare-pr-preview`**. Do not reuse
   `github-pages` or `pypi`.
2. Provision **`CLOUDFLARE_API_TOKEN`** and **`CLOUDFLARE_ACCOUNT_ID`** only on that
   Environment, with the narrowest available account/Pages upload scope.
   **No repository-level or broadly inherited organization copies.** A repository
   token would let a PR-modified build YAML steal it despite the separation here.
   Do not expose or request secret values during review.
3. Configure **no required reviewers and no manual approval gate**. No wait timer
   or custom approval rule should prevent automatic execution. Environment
   reviewers are configured in GitHub settings, never in workflow YAML.
4. Set deployment branches and tags to **Selected branches and tags**. Add exactly
   one **Branch** rule whose pattern is **`main`**. The
   [GitHub branch-policy API](https://docs.github.com/en/rest/deployments/branch-policies)
   represents this as `{ "name": "main", "type": "branch" }`. Do **not** add
   `refs/pull/*/merge`. The `workflow_run` publisher uses the default-branch ref
   as `GITHUB_REF`; the Branch rule's pattern must be `main`.
5. Turn **administrator bypass OFF**. Confirm all controls are available for the
   repository's actual plan and visibility using
   [GitHub's Environment settings guidance](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
6. Independently verify that `pluvy-preview` is the intended dedicated Direct
   Upload project, its production branch is `main`, and its Git integration,
   custom domains, and preview access settings are appropriate. Those Cloudflare
   facts have not been verified through authenticated access in this task.
7. Automatic upload can start only after the trusted publisher exists on `main`
   and these settings are complete. This PR cannot exercise `workflow_run`
   publishing from its branch.
   After those prerequisites, verify deployed headers, docs, 404s, deployment URL,
   and branch alias through an independently authorized preview. Do not trigger a
   production deployment or test live tokens from this PR.

## Production effects and local verification

`.github/workflows/deploy-website.yml` remains byte-identical to both `origin/main`
and the task's starting commit. A future merge would trigger that existing
production website workflow because website/docs paths were already changed on
this branch. Merging, deploying, changing `main`, configuring Environments, and
reading/writing secrets are outside this implementation task.

Run `python3 -m unittest discover -s .github/tests -v` for admission and artifact
security cases. Both preview build and engineering CI run this suite. It imports
and exercises the actual shared module, including positive head-tree admission,
stale heads/bases, and current merge-parent checks. The upload shell test uses a
real executable `node` script that prints arguments, never a symlink to coreutils;
it checks fixed targets and rejects invalid numbers and missing credentials
without invoking Wrangler.

With Node 22 and locked dependencies, run the website documentation-sync and
rendered favicon/base matrices. `ASTRO_BASE=/` must build correctly, and
`/favicon.svg` must stay free of a doubled slash. Run actionlint on both preview
workflows and engineering CI, then the repository's pluvy, mypy, Ruff, formatting,
and pytest checks. These checks do not validate live Cloudflare credentials,
Environment settings, runner isolation, or deployed HTTP headers. No live upload
was attempted.
