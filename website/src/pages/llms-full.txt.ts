import type { APIRoute } from 'astro';
import { buildLlmsFull } from '../llms-docs.ts';

export const GET: APIRoute = async ({ site }) => {
  const body = await buildLlmsFull(site);
  return new Response(body, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
