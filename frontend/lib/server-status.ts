/**
 * Waking the API after a quiet period (Render's free tier sleeps after ~15 minutes idle).
 *
 * While it boots (30–60 s, sometimes more), requests through the /api proxy fail with a gateway
 * error or time out. One shared loop checks /api/health every few seconds until the API answers,
 * so the banner and every waiting read share a single wake-up instead of each giving up alone.
 */

export type ServerState = "ok" | "waking" | "down";

const CHECK_TIMEOUT_MS = 20_000; // one health check
const PAUSE_MS = 3_000; // between checks
const GIVE_UP_AFTER_MS = 180_000; // the whole wake-up

const API_ORIGIN = process.env.NEXT_PUBLIC_API_ORIGIN;
const POKE_EVERY_MS = 30_000;

let state: ServerState = "ok";
let lastPoke = 0;
let pending: Promise<boolean> | null = null;
const listeners = new Set<() => void>();

function set(next: ServerState) {
  if (next === state) return;
  state = next;
  listeners.forEach((listener) => listener());
}

export function getServerState(): ServerState {
  return state;
}

export function subscribeServerState(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function healthy(): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHECK_TIMEOUT_MS);
  try {
    const response = await fetch("/api/health", { cache: "no-store", signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Render's free tier only starts a sleeping server for a direct request: requests forwarded by
 *  the Vercel proxy get an instant 502 ("no-deploy") and never wake it (measured 2026-11-11:
 *  92 s of proxied checks, all 502; one direct request woke it in 52 s). So while waiting, also
 *  ping the API's own origin. no-cors and no cookies: the answer isn't read, the request is the
 *  point. */
function pokeDirectly() {
  if (!API_ORIGIN || Date.now() - lastPoke < POKE_EVERY_MS) return;
  lastPoke = Date.now();
  fetch(`${API_ORIGIN}/api/health`, { mode: "no-cors", credentials: "omit", cache: "no-store" }).catch(() => {});
}

/** Resolves true once the API answers, false if it hasn't after three minutes. Concurrent
 *  callers share one loop. `quiet` checks once before announcing "waking" (page-load probe). */
export function waitForServer({ quiet = false }: { quiet?: boolean } = {}): Promise<boolean> {
  if (pending) return pending;
  pending = (async () => {
    const started = Date.now();
    if (!quiet) set("waking");
    // The page-load probe stays silent unless the first check is slow or fails.
    const slow = quiet ? setTimeout(() => set("waking"), 2_500) : undefined;
    try {
      while (Date.now() - started < GIVE_UP_AFTER_MS) {
        if (await healthy()) {
          set("ok");
          return true;
        }
        set("waking");
        pokeDirectly();
        await new Promise((resolve) => setTimeout(resolve, PAUSE_MS));
      }
      set("down");
      return false;
    } finally {
      clearTimeout(slow);
      pending = null;
    }
  })();
  return pending;
}
