import { loadDefaultSimplifiedChineseParser } from 'budoux';
import type { Language } from '../i18n.ts';

const parser = loadDefaultSimplifiedChineseParser();
const numberUnit = /(\d+(?:[.,]\d+)?)[ \t]+((?:ms|px|KB|MB|GB|TB|Hz|kHz|MHz|GHz)(?![A-Za-z])|个|条|次|处|行|秒|分钟|小时|字节)/gu;

export function formatText(text: string, lang: Language): string {
  const bound = text.replace(numberUnit, '$1\u00a0$2').replace(/—[ \t]+(?=Pluvy\b)/g, '—\u00a0');
  if (lang !== 'zh-CN') return bound;
  return bound
    .replace(/(\p{Script=Han})[ \t]+(?=[A-Za-z0-9])/gu, '$1')
    .replace(/([A-Za-z0-9])[ \t]+(?=\p{Script=Han})/gu, '$1');
}

export function headingPhrases(text: string, lang: Language): string[] {
  const formatted = formatText(text, lang);
  if (lang !== 'zh-CN' || !/\p{Script=Han}/u.test(formatted)) return [formatted];
  const modelText = formatted
    .replace(/(\p{Script=Han})(?=[A-Za-z0-9])/gu, '$1 ')
    .replace(/([A-Za-z0-9])(?=\p{Script=Han})/gu, '$1 ');
  let offset = 0;
  return parser.parse(modelText).map((phrase) => {
    let result = '';
    for (const character of phrase) {
      if (!formatted.startsWith(character, offset)) continue;
      result += character;
      offset += character.length;
    }
    return result;
  }).filter((phrase) => phrase.length > 0);
}

export function isChineseProse(text: string): boolean {
  const han = text.match(/\p{Script=Han}/gu)?.length ?? 0;
  const latin = text.match(/[A-Za-z]/g)?.length ?? 0;
  return han >= 40 && han > latin;
}
