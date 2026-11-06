import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ site }) => {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const base = `${import.meta.env.BASE_URL}/`;
  return rss({
    title: 'Pluvy Journal',
    description: 'Engineering notes, practical guides and release context from Pluvy.',
    site: site ?? new URL('https://sectrend-cn.github.io/pluvy/'),
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: `${base}blog/${post.id}/`,
    })),
  });
};
