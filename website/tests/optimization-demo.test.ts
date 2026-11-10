import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
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
  assert.match(before, /typeof value\.callId/);
  assert.match(before, /typeof value\.content/);
  assert.doesNotMatch(before, /\{ … \}/);
  assert.match(after, /z\.object/);
  assert.doesNotMatch(after, /function toolResultCallId/);
  assert.match(panel, /acfa790/);

  assert.doesNotMatch(panel, /RESOLVED · 305/);
});

test('finding panels reveal annotations on the same code rather than invented fixes', async () => {
  for (const kind of ['optional-fields', 'guarded-projections']) {
    const panel = await demoPanel(kind);
    const [source, annotated] = codeBlocks(panel);
    assert.ok(source);
    assert.equal(annotated, source);
    assert.match(panel, /code-line--finding/);
    assert.match(panel, /Diagnostics · same source/);
    assert.match(panel, /Suggested handoff to Agent/);
    assert.match(panel, /PLUVY/);
    assert.match(panel, /AGENT/);
    assert.doesNotMatch(panel, /class="case-evidence/);
    assert.doesNotMatch(panel, /Replay scan|comparison-controls/);
    assert.match(panel, /2026-11-09/);
    assert.match(panel, /pluvy 0\.0\.2/);
    assert.match(panel, /data-code-range/);
    assert.doesNotMatch(panel, /After · excerpt|guardedFields|every consumer/);
  }
});

test('Chinese finding panels distinguish scan evidence from unverified advice', async () => {
  for (const kind of ['optional-fields', 'guarded-projections']) {
    const panel = await demoPanel(kind, 'zh');
    assert.match(panel, /诊断标注 · 同一代码/);
    assert.match(panel, /建议示意/);
    assert.match(panel, /扫描演示/);
    assert.doesNotMatch(panel, /重新扫描|comparison-controls/);
    assert.doesNotMatch(panel, /修复后 · 节选/);
  }
});
