import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const websiteRoot = path.dirname(fileURLToPath(new URL('../package.json', import.meta.url)));
const sourceRoot = path.join(websiteRoot, '..', 'docs');
const outputRoot = path.join(websiteRoot, 'src', 'content', 'docs');
const repository = 'https://github.com/sectrend-cn/pluvy/blob/main';
const siteBase = '/pluvy';

const locales = [
  { source: sourceRoot, output: outputRoot, slugPrefix: 'docs', repositoryPrefix: '../' },
  { source: path.join(sourceRoot, 'zh'), output: path.join(outputRoot, 'zh'), slugPrefix: 'zh/docs', repositoryPrefix: '../../' },
];

function frontmatter(source, filename, slugPrefix) {
  const heading = source.match(/^#\s+(.+)$/m)?.[1] ?? filename;
  const slug = `${slugPrefix}/${filename.replace(/\.md$/, '')}`;
  return `---\ntitle: ${JSON.stringify(heading)}\nslug: ${slug}\n---\n\n`;
}

function rewriteTarget(target, locale) {
  const [file, anchor] = target.split('#');
  const suffix = anchor ? `#${anchor}` : '';
  if (file.startsWith(locale.repositoryPrefix)) {
    return `${repository}/${file.slice(locale.repositoryPrefix.length)}${suffix}`;
  }
  if (locale.slugPrefix === 'docs' && file === 'zh/getting-started.md') {
    return `${siteBase}/zh/docs/getting-started/${suffix}`;
  }
  if (locale.slugPrefix === 'zh/docs' && file === '../getting-started.md') {
    return `${siteBase}/docs/getting-started/${suffix}`;
  }
  const sibling = locale.slugPrefix === 'zh/docs' ? file.replace(/^\.\.\//, '') : file;
  if (/^[\w-]+\.md$/.test(sibling)) {
    return `${siteBase}/${locale.slugPrefix}/${sibling.replace(/\.md$/, '')}/${suffix}`;
  }
  return target;
}

function transformBody(source, locale) {
  return source
    .replace(/^#\s+.+(?:\r?\n)+/, '')
    .replace(/\]\(([^)\s]+)\)/g, (match, target) => {
      if (/^(?:[a-z]+:|#|\/)/.test(target)) return match;
      return `](${rewriteTarget(target, locale)})`;
    });
}

await rm(outputRoot, { recursive: true, force: true });
for (const locale of locales) {
  await mkdir(locale.output, { recursive: true });
  const entries = await readdir(locale.source, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) continue;
    const source = await readFile(path.join(locale.source, entry.name), 'utf8');
    const transformed = frontmatter(source, entry.name, locale.slugPrefix) + transformBody(source, locale);
    await writeFile(path.join(locale.output, entry.name), transformed);
  }
}
