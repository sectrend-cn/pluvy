import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { headingPhrases } from '../src/typography/chinese-text.ts';

const output = process.env.TYPOGRAPHY_DIST ?? 'dist';

async function page(route: string): Promise<string> {
  return readFile(path.join(output, route, 'index.html'), 'utf8');
}

test('Chinese documentation headings have phrase breaks before JavaScript runs', async () => {
  const html = await page('zh');
  const heading = html.match(/<h1\b[^>]*id="hero-title"[^>]*>(.*?)<\/h1>/s)?.[1];
  assert.ok(heading, 'the Chinese hero heading must be present');
  assert.match(heading, /<wbr\b[^>]*>/);
});

test('Chinese page titles get phrase breaks without changing their words', async () => {
  const html = await page('zh');
  const heading = html.match(/<h2\b[^>]*id="principles-title"[^>]*>(.*?)<\/h2>/s)?.[1];
  assert.ok(heading);
  assert.match(heading, /<wbr\b[^>]*>/);
  assert.equal(heading.replace(/<[^>]*>/g, '').replace(/\s/g, ''), '能过CI，却没把活干完的捷径。');
});

test('Chinese and Latin heading spacing preserves existing fragment links', async () => {
  const html = await page('docs/getting-started');
  assert.ok(html.includes('id="running"'));
  assert.ok(html.includes('id="agent-integration"'));
  assert.ok(html.includes('id="configuration"'));
  assert.ok(html.includes('id="triage"'));
});

test('number-unit pairs use nonbreaking spaces in the rendered demo', async () => {
  const html = await page('zh');
  assert.ok(/3(?:\u00a0|&#160;|&nbsp;)处违规/.test(html), 'keep 3 and 处 together');
  assert.ok(/2(?:\u00a0|&#160;|&nbsp;)条断言/.test(html), 'keep 2 and 条 together');
});

test('prose formatting leaves copyable code and English words intact', async () => {
  const english = await page('docs/getting-started');
  const code = Array.from(english.matchAll(/<pre\b[^>]*>(.*?)<\/pre>/gs), (match) => match[1]);
  assert.ok(code.length > 0);
  assert.ok(code.every((block) => !block.includes('<wbr') && !block.includes('\u00a0')));
  assert.match(english, /id="installation"[^>]*>Installation<\/h2>/);
  assert.doesNotMatch(english, /<wbr\b[^>]*>/);
});

test('mixed headings never split a Latin product name or add spaces to the copy', () => {
  assert.deepEqual(headingPhrases('pluvy快速入门', 'zh-CN'), ['pluvy', '快速入门']);
  assert.equal(headingPhrases('使用GitHub Actions检查代码', 'zh-CN').join(''), '使用GitHub Actions检查代码');
  assert.deepEqual(headingPhrases('Per-task gating', 'zh-CN'), ['Per-task gating']);
});
