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
      await writeFile(path.join(root, 'docs/getting-started.md'), '# Start\n\n[Config](checker-configuration.md#options) [中文](zh/getting-started.md) [Repo](../README.md)\n');
      await writeFile(path.join(root, 'docs/zh/getting-started.md'), '# 开始\n\n[English](../getting-started.md) [Config](../checker-configuration.md)\n');
      const env = base === undefined ? {} : { ASTRO_BASE: base };
      execFileSync(process.execPath, [path.join(website, 'scripts/sync-docs.mjs')], { env });
      const english = await readFile(path.join(website, 'src/content/docs/getting-started.md'), 'utf8');
      const chinese = await readFile(path.join(website, 'src/content/docs/zh/getting-started.md'), 'utf8');
      const prefix = base === undefined ? '/pluvy' : base.replace(/\/+$/, '');
      assert.ok(english.includes(`](${prefix}/docs/checker-configuration/#options)`));
      assert.ok(english.includes(`](${prefix}/zh/docs/getting-started/)`));
      assert.ok(english.includes('](https://github.com/sectrend-cn/pluvy/blob/main/README.md)'));
      assert.ok(chinese.includes(`](${prefix}/docs/getting-started/)`));
      assert.ok(chinese.includes(`](${prefix}/zh/docs/checker-configuration/)`));
      assert.doesNotMatch(english + chinese, /\]\(\/\/(?:docs|zh)\//);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
}
