import sitemap from '@astrojs/sitemap';
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://sectrend-cn.github.io',
  base: '/pluvy',
  output: 'static',
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
        Pagination: './src/components/docs/DocsPagination.astro',
      },
      disable404Route: true,
      sidebar: [
        {
          label: 'Start',
          items: [{ label: 'Getting started', slug: 'docs/getting-started' }],
        },
        {
          label: 'Configure & Run',
          items: [
            { label: 'Checker configuration', slug: 'docs/checker-configuration' },
            { label: 'Diagnostic exceptions', slug: 'docs/comment-suppressions' },
          ],
        },
        {
          label: 'Integrate',
          items: [{ label: 'Agent review', slug: 'docs/agent-review' }],
        },
        {
          label: 'Design & Reference',
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
