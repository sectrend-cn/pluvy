import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

for (const base of [undefined, '/', '/pluvy', '/nested/site/']) {
  test(`sync-docs rewrites sibling and locale links for ASTRO_BASE=${base ?? '(default)'}`, async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'pluvy-sync-docs-'));
    try {
      const website = path.join(root, 'website');
      await mkdir(path.join(website, 'scripts'), { recursive: true });
      await mkdir(path.join(root, 'docs', 'zh'), { recursive: true });
      await cp(new URL('../scripts/sync-docs.mjs', import.meta.url), path.join(website, 'scripts/sync-docs.mjs'));
      await writeFile(path.join(root, 'docs/getting-started.md'), '# Start\n\n[Config](checker-configuration.md#options) [Repo](../README.md)\n');
      await writeFile(path.join(root, 'docs/cloudflare-pr-preview.md'), '# Internal preview\n\nOps verification only.\n');
      await writeFile(path.join(root, 'docs/zh/getting-started.md'), '# Legacy Chinese\n');
      const env = base === undefined ? {} : { ASTRO_BASE: base };
      execFileSync(process.execPath, [path.join(website, 'scripts/sync-docs.mjs')], { env });
      const english = await readFile(path.join(website, 'src/content/docs/getting-started.md'), 'utf8');
      await assert.rejects(readFile(path.join(website, 'src/content/docs/cloudflare-pr-preview.md'), 'utf8'));
      await assert.rejects(readFile(path.join(website, 'src/content/docs/zh/getting-started.md'), 'utf8'));
      const prefix = base === undefined ? '/pluvy' : base.replace(/\/+$/, '');
      assert.ok(english.includes(`](${prefix}/docs/checker-configuration/#options)`));
      assert.ok(english.includes('](https://github.com/sectrend-cn/pluvy/blob/main/README.md)'));
      assert.doesNotMatch(english, /\]\(\/\/docs\//);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
}
