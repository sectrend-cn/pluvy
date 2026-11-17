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
    assert.equal(annotated, source);
    assert.match(panel, /code-line--finding/);
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
    assert.match(panel, /诊断标注 · 同一代码/);
    assert.match(panel, /门禁返回给 Agent 的修复要求/);
    assert.match(panel, /门禁拦截 · exit 1/);
    assert.doesNotMatch(panel, /修复后 · 节选/);
  }
});

test('Chinese docs shell is localized and non-public files are excluded from build output', async () => {
  const zhDocs = await readFile(path.join(output, 'zh/docs/getting-started/index.html'), 'utf8');
  assert.match(zhDocs, /遇到问题？/);
  assert.match(zhDocs, /报告误报/);
  assert.match(zhDocs, /上一页/);
  assert.match(zhDocs, /文档目录/);
  assert.match(zhDocs, /本页目录/);
  assert.match(zhDocs, /href="\/pluvy\/zh\/"\s+rel="prev"/);
  assert.doesNotMatch(zhDocs, /github\.com\/sectrend-cn\/pluvy\/discussions/);
  await assert.rejects(access(path.join(output, 'docs/cloudflare-pr-preview/index.html')));
  await assert.rejects(access(path.join(output, 'animations/crocodile.html')));
  await assert.rejects(access(path.join(output, 'images/pluvy-bird.svg')));
});
