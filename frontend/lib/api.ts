/**
 * The only way the browser talks to the backend: relative /api/* (same origin, proxied by
 * Next.js to FastAPI). Errors arrive as {"error": {"code", "message"}} and are surfaced as
 * ApiError so screens can translate by code (ARCHITECTURE §2).
 */

import { waitForServer } from "@/lib/server-status";

export type Role = "homeowner" | "sales" | "admin";

export type UserOut = {
  id: string;
  full_name: string;
  role: Role;
  email: string | null;
  phone_masked: string | null;
  preferred_locale: "en" | "hi" | "mr";
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** No answer, or a proxy error page instead of the API's own `{"error": …}` body: the API isn't
 *  up yet (asleep or booting), as opposed to the API answering with an error. */
async function looksAsleep(response: Response | null): Promise<boolean> {
  if (!response) return true;
  if (response.status < 500) return false;
  const body = await response.clone().json().catch(() => null);
  return !body?.error?.code;
}

type ApiInit = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const method = (rest.method ?? (json !== undefined ? "POST" : "GET")).toUpperCase();
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  if (json !== undefined) finalHeaders.set("Content-Type", "application/json");
  if (UNSAFE.has(method)) finalHeaders.set("X-HF-CSRF", "1");

  const send = async (): Promise<Response | null> => {
    try {
      return await fetch(path, {
        ...rest,
        method,
        headers: finalHeaders,
        body: json !== undefined ? JSON.stringify(json) : rest.body,
        credentials: "same-origin",
      });
    } catch {
      return null; // network error
    }
  };

  let response = await send();
  // The API may be asleep (free hosting). A read waits for it to wake and is asked again once.
  // A write is never repeated automatically: the first attempt may still have reached the API.
  if (!UNSAFE.has(method) && (await looksAsleep(response)) && (await waitForServer())) {
    response = await send();
  }
  if (!response) throw new ApiError(0, "NETWORK", "Network error");

  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = payload?.error;
    throw new ApiError(response.status, error?.code ?? "UNKNOWN", error?.message ?? response.statusText);
  }
  return payload as T;
}

/** Only allow same-site relative paths as post-login destinations (no open redirects). */
export function safeNextPath(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return null;
  return next;
}
