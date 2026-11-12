import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const website = fileURLToPath(new URL('../', import.meta.url));
const astro = fileURLToPath(new URL('../node_modules/astro/bin/astro.mjs', import.meta.url));
const cases = [
  { name: 'root base', base: '/', favicon: '/favicon.svg' },
  { name: 'default GitHub Pages base', base: undefined, favicon: '/pluvy/favicon.svg' },
  { name: 'nested base', base: '/nested/site', favicon: '/nested/site/favicon.svg' },
  { name: 'trailing-slash base', base: '/nested/site/', favicon: '/nested/site/favicon.svg' },
];

for (const { name, base, favicon } of cases) {
  test(`${name} renders a favicon on the preview origin`, async () => {
    const output = await mkdtemp(path.join(os.tmpdir(), 'pluvy-favicon-'));
    try {
      const env = { PATH: `${path.dirname(process.execPath)}:/usr/bin:/bin`, CI: 'true' };
      execFileSync(process.execPath, [astro, 'build', '--outDir', output], {
        cwd: website,
        env: base === undefined ? env : { ...env, ASTRO_BASE: base },
        timeout: 60_000,
        stdio: 'pipe',
      });
      await access(path.join(output, 'favicon.svg'));
      for (const route of ['index.html', 'zh/index.html', 'blog/index.html', '404.html']) {
        const html = await readFile(path.join(output, route), 'utf8');
        const href = html.match(/<link\b[^>]*\brel="icon"[^>]*\bhref="([^"]+)"/)?.[1];
        assert.ok(href, `${route} must declare its favicon`);
        assert.equal(href, favicon, `${route} must respect its configured base`);
        assert.equal(new URL(href, 'https://preview.example').origin, 'https://preview.example');
      }
    } finally {
      await rm(output, { recursive: true, force: true });
    }
  });
}
