import type { HastNode, HastPluginDefinition, HastVisitorContext, PluginFactoryContext } from 'satteri';
import Slugger from 'github-slugger';
import { formatText, headingPhrases, isChineseProse } from './chinese-text.ts';
import type { Language } from '../i18n.ts';

type ElementNode = Extract<HastNode, { type: 'element' }>;
type HeadingChild = ElementNode['children'][number];

function headingChildren(node: HeadingChild): HeadingChild[] {
  if (node.type === 'text') {
    return headingPhrases(node.value, 'zh-CN').flatMap((phrase, index): HeadingChild[] => {
      const text: HeadingChild = { type: 'text', value: phrase };
      return index === 0 ? [text] : [
        { type: 'element', tagName: 'wbr', properties: { dataPhraseBreak: true }, children: [] },
        text,
      ];
    });
  }
  if (node.type === 'element' && node.tagName !== 'code') {
    return [{ ...node, children: node.children.flatMap(headingChildren) }];
  }
  return [node];
}

function isLiteral(node: Readonly<HastNode>, context: HastVisitorContext): boolean {
  let parent = context.parent(node);
  while (parent) {
    if (parent.type === 'element' && ['pre', 'code', 'kbd', 'samp', 'script', 'style', 'h1', 'h2', 'h3'].includes(parent.tagName)) return true;
    parent = context.parent(parent);
  }
  return false;
}

export function typographyMarkdown({ fileURL }: PluginFactoryContext): HastPluginDefinition {
  const lang: Language = fileURL?.pathname.includes('/zh/') ? 'zh-CN' : 'en';
  const slugger = new Slugger();
  return {
    name: 'pluvy-typography',
    element: [
      {
        filter: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
        visit(node, context) {
          if (lang !== 'zh-CN') return;
          const id = node.properties?.id;
          const properties = { ...node.properties, id: typeof id === 'string' ? id : slugger.slug(context.textContent(node)) };
          const children = ['h1', 'h2', 'h3'].includes(node.tagName) ? node.children.flatMap(headingChildren) : node.children;
          return { ...node, properties, children };
        },
      },
      {
        filter: ['p'],
        visit(node, context) {
          if (lang === 'zh-CN' && isChineseProse(context.textContent(node))) {
            context.setProperty(node, 'data-zh-prose', true);
          }
        },
      },
    ],
    text(node, context) {
      if (isLiteral(node, context)) return;
      const value = formatText(node.value, lang);
      if (value !== node.value) return { ...node, value };
    },
  };
}
