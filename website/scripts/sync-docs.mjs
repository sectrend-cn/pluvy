import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const websiteRoot = path.dirname(fileURLToPath(new URL('../package.json', import.meta.url)));
const sourceRoot = path.join(websiteRoot, '..', 'docs');
const outputRoot = path.join(websiteRoot, 'src', 'content', 'docs');
const repository = 'https://github.com/sectrend-cn/pluvy/blob/main';

function frontmatter(source, filename) {
  const heading = source.match(/^#\s+(.+)$/m)?.[1] ?? filename;
  const slug = `docs/${filename.replace(/\.md$/, '')}`;
  return `---\ntitle: ${JSON.stringify(heading)}\nslug: ${slug}\n---\n\n`;
}

function transformBody(source) {
  return source.replace(/^#\s+.+(?:\r?\n)+/, '')
    .replaceAll('../README.md', `${repository}/README.md`)
    .replaceAll('../examples/', `${repository}/examples/`)
    .replaceAll('../.agents/', `${repository}/.agents/`)
    .replaceAll('zh/getting-started.md', `${repository}/docs/zh/getting-started.md`);
}

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });
const entries = await readdir(sourceRoot, { withFileTypes: true });
for (const entry of entries) {
  if (!entry.isFile() || !entry.name.endsWith('.md')) continue;
  const source = await readFile(path.join(sourceRoot, entry.name), 'utf8');
  const transformed = frontmatter(source, entry.name) + transformBody(source);
  await writeFile(path.join(outputRoot, entry.name), transformed);
}
