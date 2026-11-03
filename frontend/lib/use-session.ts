"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { clearDraft } from "@/components/lead-form/draft";
import { api, ApiError, type UserOut } from "@/lib/api";

export const SESSION_KEY = ["session"] as const;

/** Where "home" is for each person: staff work in the inbox, homeowners in My solar. */
export function homeFor(user: UserOut | null): "/staff/leads" | "/my" | "/" {
  if (!user) return "/";
  return user.role === "homeowner" ? "/my" : "/staff/leads";
}

async function fetchSession(): Promise<UserOut | null> {
  try {
    return await api<UserOut>("/api/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

/**
 * Only a confirmed 401 means "signed out". Anything else (cold-start timeout, 5xx, network)
 * is an error the screen must show with a retry — never a reason to send a signed-in person
 * back to sign-in.
 */
export function useSession() {
  const query = useQuery({
    queryKey: SESSION_KEY,
    queryFn: fetchSession,
    staleTime: 60_000,
    // A sleeping backend (free tier) may need a couple of attempts; 401 is never retried.
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 2,
    retryDelay: 3000,
  });
  return {
    user: query.data ?? null,
    isLoading: query.isPending,
    error: query.isError ? query.error : null,
    refetch: query.refetch,
  };
}

/** Signs out, then does a full page load of the landing page. The hard navigation clears all
 * client state and avoids racing the session guards' own redirect to sign-in. */
export function useSignOut() {
  const client = useQueryClient();
  return async (locale: string) => {
    await api<void>("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    client.cancelQueries();
    clearDraft(); // an unfinished form must not follow the next person using this device
    // Deliberate full load (not router.push): drops every cached query holding personal data
    // and prevents RequireSession's sign-in redirect from racing this navigation.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/${locale}`);
  };
}
