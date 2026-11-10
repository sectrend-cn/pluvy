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
  const html = await page('zh/docs/getting-started');
  const heading = html.match(/<h3\b[^>]*id="存量仓库的首次全量审计"[^>]*>(.*?)<\/h3>/s)?.[1];
  assert.ok(heading, 'the original heading and fragment URL must remain present');
  assert.match(heading, /<wbr\b[^>]*>/);
  assert.equal(heading.replace(/<[^>]*>/g, ''), '存量仓库的首次全量审计');
});

test('Chinese page titles get phrase breaks without changing their words', async () => {
  const html = await page('zh/docs/getting-started');
  const heading = html.match(/<h1\b[^>]*id="_top"[^>]*>(.*?)<\/h1>/s)?.[1];
  assert.ok(heading);
  assert.match(heading, /<wbr\b[^>]*>/);
  assert.equal(heading.replace(/<[^>]*>/g, '').replace(/\s/g, ''), 'pluvy快速入门');
});

test('Chinese and Latin heading spacing preserves existing fragment links', async () => {
  const html = await page('zh/docs/getting-started');
  assert.ok(html.includes('id="从-pypi-安装"'));
  assert.ok(html.includes('id="skill-获取"'));
});

test('number-unit pairs use nonbreaking spaces in the rendered demo', async () => {
  const html = await page('zh');
  assert.ok(/7(?:\u00a0|&#160;|&nbsp;)次/.test(html), 'keep 7 and 次 together');
  assert.ok(/6(?:\u00a0|&#160;|&nbsp;)个可选字段/.test(html), 'keep 6 and 个 together');
});

test('prose formatting leaves copyable code and English words intact', async () => {
  const chinese = await page('zh/docs/getting-started');
  const english = await page('docs/getting-started');
  const code = Array.from(chinese.matchAll(/<pre\b[^>]*>(.*?)<\/pre>/gs), (match) => match[1]);
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
