import type { APIRoute } from 'astro';
import { buildLlmsIndex } from '../llms-docs.ts';

export const GET: APIRoute = async ({ site }) => {
  const body = await buildLlmsIndex(site);
  return new Response(body, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
