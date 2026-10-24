/**
 * Server-side env access for the GTM data layer.
 * All vars are server-only (no NEXT_PUBLIC_ prefix) — never shipped to the browser.
 */

export function optionalEnv(name: string): string | null {
  const v = process.env[name];
  return v && v.trim() !== '' ? v : null;
}

export function requiredEnv(name: string): string {
  const v = optionalEnv(name);
  if (!v)
    throw new Error(
      `Missing required environment variable ${name}. See env.example.txt for the GTM data layer configuration.`
    );
  return v;
}
