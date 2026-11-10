import sitemap from '@astrojs/sitemap';
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';
import { satteri } from '@astrojs/markdown-satteri';
import { typographyMarkdown } from './src/typography/markdown.ts';

export default defineConfig({
  site: 'https://sectrend-cn.github.io',
  base: process.env.ASTRO_BASE ?? '/pluvy',
  output: 'static',
  markdown: {
    processor: satteri({ hastPlugins: [typographyMarkdown] }),
  },
  integrations: [
    starlight({
      title: 'Pluvy',
      description: 'A read-only, parser-backed engineering policy gate.',
      logo: {
        src: './src/assets/pluvy-natural-neck.svg',
        alt: 'Pluvy',
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/sectrend-cn/pluvy',
        },
      ],
      head: [
        {
          tag: 'script',
          attrs: {},
          content: `
            try {
              const preference = localStorage.getItem('pluvy-theme');
              if (preference === 'dark' || preference === 'light') {
                document.documentElement.dataset.theme = preference;
                localStorage.setItem('starlight-theme', preference);
              }
              const observer = new MutationObserver(() => {
                const selected = localStorage.getItem('starlight-theme');
                if (selected === 'dark' || selected === 'light') localStorage.setItem('pluvy-theme', selected);
                else localStorage.removeItem('pluvy-theme');
                document.querySelector('meta[name="theme-color"]')?.setAttribute(
                  'content',
                  document.documentElement.dataset.theme === 'dark' ? '#111210' : '#f8faf8',
                );
              });
              observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
            } catch {}
          `,
        },
      ],
      customCss: ['./src/styles/starlight.css', './src/styles/typography.css', './src/styles/docs-layout.css'],
      components: {
        Head: './src/components/docs/TypographyHead.astro',
        PageTitle: './src/components/docs/TypographyPageTitle.astro',
        Pagination: './src/components/docs/DocsPagination.astro',
      },
      disable404Route: true,
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        zh: { label: '简体中文', lang: 'zh-CN' },
      },
      sidebar: [
        {
          label: 'Start',
          translations: { 'zh-CN': '开始' },
          items: [{ label: 'Getting started', translations: { 'zh-CN': '快速入门' }, slug: 'docs/getting-started' }],
        },
        {
          label: 'Configure & Run',
          translations: { 'zh-CN': '配置与运行' },
          items: [
            { label: 'Checker configuration', slug: 'docs/checker-configuration' },
            { label: 'Diagnostic exceptions', slug: 'docs/comment-suppressions' },
          ],
        },
        {
          label: 'Design & Reference',
          translations: { 'zh-CN': '设计与参考' },
          items: [
            { label: 'Engineering standards', slug: 'docs/engineering-standards' },
            { label: 'Plugin architecture', slug: 'docs/plugin-architecture' },
            { label: 'Go field consumption', slug: 'docs/go-consumed-fields' },
          ],
        },
      ],
    }),
    sitemap(),
  ],
});
