import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { getCollection } from 'astro:content';
import { basePath } from './i18n.ts';

export interface DocPageSpec {
  readonly slug: string;
  readonly filename: string;
  readonly summary: string;
}

const repoRoot = existsSync(path.join(process.cwd(), 'docs', 'getting-started.md'))
  ? process.cwd()
  : path.resolve(process.cwd(), '..');
const docsRoot = path.join(repoRoot, 'docs');
const githubBlobRoot = 'https://github.com/sectrend-cn/pluvy/blob/main';

export const docPages: readonly DocPageSpec[] = [
  {
    slug: 'getting-started',
    filename: 'getting-started.md',
    summary: 'Install Pluvy, bootstrap .pluvy/pluvy.json, run --all / --base / --staged, triage findings, and connect coding agents.',
  },
  {
    slug: 'checker-configuration',
    filename: 'checker-configuration.md',
    summary: 'Policy schema, all 22 built-in checkers and 29 diagnostic IDs, per-language coverage, deletion gate, and source placement.',
  },
  {
    slug: 'serialization-boundaries',
    filename: 'serialization-boundaries.md',
    summary: 'Directional third_party_modules boundaries, cross-file usage resolution, built-in JSON serializers, and type.broad.encoding options.',
  },
  {
    slug: 'comment-suppressions',
    filename: 'comment-suppressions.md',
    summary: 'Syntax, human-approval requirements, and validation rules for next-line diagnostic exceptions across all supported languages.',
  },
  {
    slug: 'engineering-standards',
    filename: 'engineering-standards.md',
    summary: 'Shared engineering policy and the division between automated Pluvy checks and code-review obligations.',
  },
  {
    slug: 'plugin-architecture',
    filename: 'plugin-architecture.md',
    summary: 'Decoupled tree-sitter language adapters, rule bundles, changed-scope filtering, and checker-owned registration.',
  },
  {
    slug: 'go-consumed-fields',
    filename: 'go-consumed-fields.md',
    summary: 'How Go usage analysis recognizes implicit struct field reads in serialization, reflect.DeepEqual, and structural equality.',
  },
];

export function siteRootUrl(site: URL | undefined): string {
  const origin = (site ?? new URL('https://sectrend-cn.github.io')).origin;
  return `${origin}${basePath()}`;
}

function resolveDocLink(target: string, rootUrl: string): string {
  const [file = '', anchor] = target.split('#');
  const suffix = anchor ? `#${anchor}` : '';
  if (file.startsWith('../')) {
    return `${githubBlobRoot}/${file.slice(3)}${suffix}`;
  }
  if (/^[\w-]+\.md$/.test(file)) {
    return `${rootUrl}docs/${file}${suffix}`;
  }
  return target;
}

export async function renderDocMarkdown(filename: string, rootUrl: string): Promise<string> {
  const raw = await readFile(path.join(docsRoot, filename), 'utf8');
  return raw.replace(/\]\(([^)\s]+)\)/g, (match, target: string) => {
    if (/^(?:[a-z]+:|#|\/)/.test(target)) return match;
    return `](${resolveDocLink(target, rootUrl)})`;
  });
}

export async function buildLlmsIndex(site: URL | undefined): Promise<string> {
  const rootUrl = siteRootUrl(site);
  const posts = (await getCollection('blog', ({ data }) => !data.draft))
    .sort((left, right) => right.data.pubDate.getTime() - left.data.pubDate.getTime());
  const docLines = docPages.map(
    (doc) => `- [${doc.slug}](${rootUrl}docs/${doc.filename}): ${doc.summary}`,
  );
  const postLines = posts.map(
    (post) => `- [${post.data.title}](${rootUrl}blog/${post.id}/): ${post.data.description}`,
  );
  return [
    '# Pluvy',
    '',
    '> Pluvy is a read-only, parser-backed engineering policy gate for Python, Go, Java, JavaScript/JSX, and TypeScript/TSX. It checks code written by people and coding agents against a repository\'s committed `.pluvy/pluvy.json` policy and fails the check when a change erases type contracts, suppresses diagnostics, swallows errors, weakens or deletes tests, or crosses declared architecture boundaries.',
    '',
    'Key CLI facts:',
    '- Modes (mutually exclusive): `pluvy --all`, `pluvy --base <commit>`, `pluvy --staged`',
    '- Options: `--root <dir>` (default `.`), `--config <path>` (default `.pluvy/pluvy.json`), `--format text|json`',
    '- Exit codes: `0` pass (warnings allowed), `1` error findings present, `2` configuration/filesystem/Git failure',
    '- Read-only guarantee: Pluvy never edits, stages, stashes, restores, or deletes files, and never modifies Git configuration.',
    '',
    '## Complete corpus',
    '',
    `- [Full documentation (single file)](${rootUrl}llms-full.txt): Plain-text bundle of all Pluvy documentation, sample policy, and bundled agent skill.`,
    '',
    '## Documentation (Markdown)',
    '',
    ...docLines,
    '',
    '## Agent skill & sample policy',
    '',
    `- [Agent skill (SKILL.md)](${githubBlobRoot}/.agents/skills/pluvy/SKILL.md): Post-task gate workflow, command selection table, triage rules, and per-language checker matrix.`,
    `- [Checker index](${githubBlobRoot}/.agents/skills/pluvy/references/checkers.md): Per-checker option and diagnostic reference pages.`,
    `- [Example policy](${githubBlobRoot}/examples/.pluvy/pluvy.json): Starter .pluvy/pluvy.json declaring owners, import boundaries, encoding rules, and function limits.`,
    '',
    '## Blog',
    '',
    ...postLines,
    '',
  ].join('\n');
}

export async function buildLlmsFull(site: URL | undefined): Promise<string> {
  const rootUrl = siteRootUrl(site);
  const sections: string[] = [await buildLlmsIndex(site)];
  for (const doc of docPages) {
    const body = await renderDocMarkdown(doc.filename, rootUrl);
    sections.push(`---\nSource: ${rootUrl}docs/${doc.filename}\n\n${body.trim()}`);
  }
  const samplePolicy = await readFile(path.join(repoRoot, 'examples/.pluvy/pluvy.json'), 'utf8');
  sections.push(
    `---\nSource: ${githubBlobRoot}/examples/.pluvy/pluvy.json\n\n# Example .pluvy/pluvy.json\n\n\`\`\`json\n${samplePolicy.trim()}\n\`\`\``,
  );
  const skill = await readFile(path.join(repoRoot, '.agents/skills/pluvy/SKILL.md'), 'utf8');
  sections.push(`---\nSource: ${githubBlobRoot}/.agents/skills/pluvy/SKILL.md\n\n${skill.trim()}`);
  return `${sections.join('\n\n')}\n`;
}
