import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIRoute } from 'astro';
import { basePath } from '../i18n.ts';

export const GET: APIRoute = async ({ site }) => {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const base = basePath();
  return rss({
    title: 'Pluvy Blog',
    description: 'Design decisions and engineering essays from Pluvy.',
    site: site ?? new URL('https://sectrend-cn.github.io/pluvy/'),
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: `${base}blog/${post.id}/`,
    })),
  });
};
