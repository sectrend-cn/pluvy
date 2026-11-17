import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const websiteRoot = path.dirname(fileURLToPath(new URL('../package.json', import.meta.url)));
const sourceRoot = path.join(websiteRoot, '..', 'docs');
const outputRoot = path.join(websiteRoot, 'src', 'content', 'docs');
const repository = 'https://github.com/sectrend-cn/pluvy/blob/main';
const siteBase = (process.env.ASTRO_BASE ?? '/pluvy').replace(/\/+$/, '');

const publishedDocs = new Set([
  'getting-started.md',
  'checker-configuration.md',
  'serialization-boundaries.md',
  'comment-suppressions.md',
  'engineering-standards.md',
  'plugin-architecture.md',
  'go-consumed-fields.md',
]);

function frontmatter(source, filename) {
  const heading = (source.match(/^#\s+(.+)$/m)?.[1] ?? filename).replaceAll('\\', '\\\\').replaceAll('"', '\\"');
  const slug = `docs/${filename.replace(/\.md$/, '')}`;
  return `---\ntitle: "${heading}"\nslug: ${slug}\n---\n\n`;
}

function rewriteTarget(target) {
  const [file, anchor] = target.split('#');
  const suffix = anchor ? `#${anchor}` : '';
  if (file.startsWith('../')) {
    return `${repository}/${file.slice(3)}${suffix}`;
  }
  if (/^[\w-]+\.md$/.test(file)) {
    return `${siteBase}/docs/${file.replace(/\.md$/, '')}/${suffix}`;
  }
  return target;
}

function transformBody(source) {
  return source
    .replace(/^#\s+.+(?:\r?\n)+/, '')
    .replace(/\]\(([^)\s]+)\)/g, (match, target) => {
      if (/^(?:[a-z]+:|#|\/)/.test(target)) return match;
      return `](${rewriteTarget(target)})`;
    });
}

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });
const entries = await readdir(sourceRoot, { withFileTypes: true });
for (const entry of entries) {
  if (!entry.isFile() || !publishedDocs.has(entry.name)) continue;
  const source = await readFile(path.join(sourceRoot, entry.name), 'utf8');
  const transformed = frontmatter(source, entry.name) + transformBody(source);
  await writeFile(path.join(outputRoot, entry.name), transformed);
}
