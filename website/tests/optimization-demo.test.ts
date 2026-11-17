import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

const output = process.env.TYPOGRAPHY_DIST ?? 'dist';

async function demoPanel(kind: string, route = ''): Promise<string> {
  const html = await readFile(path.join(output, route, 'index.html'), 'utf8');
  const panel = Array.from(html.matchAll(/<article\b[^>]*data-case-kind="([^"]+)"[^>]*>(.*?)<\/article>/gs))
    .find((match) => match[1] === kind)?.[2];
  assert.ok(panel, `rendered ${kind} panel must exist`);
  return panel;
}

function codeBlocks(panel: string): string[] {
  return Array.from(panel.matchAll(/<pre\b[^>]*>(.*?)<\/pre>/gs), (match) => match[1].replace(/<[^>]*>/g, ''));
}

test('the recorded refactor shows the repeated guards and source commit', async () => {
  const panel = await demoPanel('resolved');
  const [before, after] = codeBlocks(panel);
  assert.ok(before);
  assert.ok(after);
  assert.match(before, /@ts-ignore/);
  assert.match(before, /raw: any/);
  assert.match(before, /catch \(error\)/);
  assert.match(after, /export interface Order/);
  assert.doesNotMatch(after, /@ts-ignore|raw: any/);
  assert.match(panel, /Resolved · exit 0/);
});

test('finding panels reveal annotations on the same code rather than invented fixes', async () => {
  for (const kind of ['test-integrity', 'boundary-drift']) {
    const panel = await demoPanel(kind);
    const [source, annotated] = codeBlocks(panel);
    assert.ok(source);
    assert.ok(annotated);
    assert.doesNotMatch(source, /\/\/ (?:test\.|architecture\.|type\.)/);
    assert.match(annotated, /\/\/ (?:test\.|architecture\.|type\.)/);
    assert.match(panel, /code-line--finding/);
    assert.match(panel, /code-line__note/);
    assert.doesNotMatch(panel, /agent-advice__pending/);
    assert.match(panel, /Diagnostics · same source/);
    assert.match(panel, /Gate feedback returned to Agent/);
    assert.match(panel, /Blocked · exit 1/);
    assert.match(panel, /PLUVY/);
    assert.match(panel, /AGENT/);
    assert.match(panel, /data-code-range/);
    assert.doesNotMatch(panel, /After · excerpt/);
  }
});

test('Chinese finding panels distinguish scan evidence from unverified advice', async () => {
  for (const kind of ['test-integrity', 'boundary-drift']) {
    const panel = await demoPanel(kind, 'zh');
    const [source, annotated] = codeBlocks(panel);
    assert.ok(source);
    assert.ok(annotated);
    assert.doesNotMatch(source, /\/\/ (?:test\.|architecture\.|type\.)/);
    assert.match(annotated, /\/\/ (?:test\.|architecture\.|type\.)/);
    assert.match(panel, /诊断标注 · 同一代码/);
    assert.match(panel, /门禁返回给 Agent 的修复要求/);
    assert.match(panel, /门禁拦截 · exit 1/);
    assert.doesNotMatch(panel, /agent-advice__pending/);
    assert.doesNotMatch(panel, /修复后 · 节选/);
  }
});

test('docs are English-only with agent-friendly llms.txt and raw Markdown outputs', async () => {
  const enLanding = await readFile(path.join(output, 'index.html'), 'utf8');
  assert.match(enLanding, /class="github-icon[^"]*"/);
  assert.doesNotMatch(enLanding, /Hold new changes to the policy/);
  assert.doesNotMatch(enLanding, />llms-full\.txt</);

  const zhLanding = await readFile(path.join(output, 'zh/index.html'), 'utf8');
  assert.match(zhLanding, /href="\/pluvy\/docs\/getting-started\/"/);
  assert.match(zhLanding, /class="github-icon[^"]*"/);
  assert.doesNotMatch(zhLanding, /新改动按策略把关/);
  assert.doesNotMatch(zhLanding, />llms-full\.txt</);
  assert.doesNotMatch(zhLanding, /\/zh\/docs\//);

  const enDocs = await readFile(path.join(output, 'docs/getting-started/index.html'), 'utf8');
  assert.match(enDocs, /For agents:/);
  assert.match(enDocs, /href="\/pluvy\/docs\/getting-started\.md"/);
  assert.match(enDocs, /href="\/pluvy\/llms\.txt"/);
  assert.doesNotMatch(enDocs, />llms-full\.txt</);
  assert.doesNotMatch(enDocs, /github\.com\/sectrend-cn\/pluvy\/discussions/);

  const llmsTxt = await readFile(path.join(output, 'llms.txt'), 'utf8');
  assert.match(llmsTxt, /^# Pluvy/m);
  assert.match(llmsTxt, /https:\/\/sectrend-cn\.github\.io\/pluvy\/llms-full\.txt/);
  assert.match(llmsTxt, /https:\/\/sectrend-cn\.github\.io\/pluvy\/docs\/getting-started\.md/);

  const llmsFull = await readFile(path.join(output, 'llms-full.txt'), 'utf8');
  assert.match(llmsFull, /# Pluvy getting started/);
  assert.match(llmsFull, /# Checker configuration/);
  assert.match(llmsFull, /# Boundaries, usage and serialization/);

  const rawDoc = await readFile(path.join(output, 'docs/getting-started.md'), 'utf8');
  assert.match(rawDoc, /^# Pluvy getting started/m);

  await assert.rejects(access(path.join(output, 'zh/docs/getting-started/index.html')));
  await assert.rejects(access(path.join(output, 'docs/cloudflare-pr-preview/index.html')));
  await assert.rejects(access(path.join(output, 'animations/crocodile.html')));
  await assert.rejects(access(path.join(output, 'images/pluvy-bird.svg')));
});
