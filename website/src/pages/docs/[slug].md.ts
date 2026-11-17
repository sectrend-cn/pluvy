import type { APIRoute, GetStaticPaths } from 'astro';
import { docPages, renderDocMarkdown, siteRootUrl } from '../../llms-docs.ts';

export const getStaticPaths: GetStaticPaths = () =>
  docPages.map((doc) => ({ params: { slug: doc.slug } }));

export const GET: APIRoute = async ({ params, site }) => {
  const doc = docPages.find((entry) => entry.slug === params.slug);
  if (!doc) return new Response('Not found', { status: 404 });
  const body = await renderDocMarkdown(doc.filename, siteRootUrl(site));
  return new Response(body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};
