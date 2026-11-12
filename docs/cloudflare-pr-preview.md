# Cloudflare PR previews: native Git integration

Cloudflare Pages native Git integration now supplies PR previews for
`sectrend-cn/pluvy`. It replaces the self-built preview publisher; Ops has
already stopped the old self-built workflows.

## Ops-verified configuration

| Setting | Verified value |
| --- | --- |
| Cloudflare Pages project | `pluvy-git-preview` |
| GitHub repository | `sectrend-cn/pluvy` |
| Watch paths | `website/*` and `docs/*` |
| Production deployments | `production_deployments_enabled=false` |
| Preview branches | All |
| PR comments | `pr_comments=true` |

## Verification and remaining observation

Ops verified the native preview for PR #24: HTTP 200 and noindex. The
[Cloudflare bot comment](https://github.com/sectrend-cn/pluvy/pull/24#issuecomment-6822663948)
records its preview link.

Existing PRs were started with an `ad_hoc` launch. **Natural watch has not been
empirically tested.** The existing preview verification does not establish that
path-based watching launches new previews. A subsequent website/docs PR can
let Ops observe natural watch.

## Production and documentation

Production deployments are disabled for this Cloudflare Pages project. The
existing production website workflow, `.github/workflows/deploy-website.yml`,
is unchanged by the preview cleanup.

The website documentation sync copies this file from `docs/` during its build,
so this file is the source for the published preview documentation.
