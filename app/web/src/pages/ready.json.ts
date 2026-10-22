export function GET(): Response {
  const ready = import.meta.env.PUBLIC_API_READY === 'true';
  return new Response(JSON.stringify({ ready }), { headers: { 'Content-Type': 'application/json' } });
}
