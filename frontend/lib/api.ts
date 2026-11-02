/**
 * The only way the browser talks to the backend: relative /api/* (same origin, proxied by
 * Next.js to FastAPI). Errors arrive as {"error": {"code", "message"}} and are surfaced as
 * ApiError so screens can translate by code (ARCHITECTURE §2).
 */

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

type ApiInit = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const method = (rest.method ?? (json !== undefined ? "POST" : "GET")).toUpperCase();
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  if (json !== undefined) finalHeaders.set("Content-Type", "application/json");
  if (UNSAFE.has(method)) finalHeaders.set("X-HF-CSRF", "1");

  let response: Response;
  try {
    response = await fetch(path, {
      ...rest,
      method,
      headers: finalHeaders,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Network error");
  }

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
