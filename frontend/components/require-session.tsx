"use client";

import { CloudOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePathname, useRouter } from "@/i18n/navigation";
import { ApiError, type UserOut } from "@/lib/api";
import { useSession } from "@/lib/use-session";

/**
 * UX-only guard: the API is the real gate (§4). Redirects to sign-in exactly once, and only
 * when the server confirms there is no session (401). Other failures show an error with retry.
 */
export function RequireSession({ children }: { children: (user: UserOut) => ReactNode }) {
  const { user, isLoading, error, refetch } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const redirected = useRef(false);
  const te = useTranslations("errors");
  const tc = useTranslations("common");

  const signedOut = !isLoading && !error && !user;

  useEffect(() => {
    if (signedOut && !redirected.current) {
      redirected.current = true;
      router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
    }
  }, [signedOut, pathname, router]);

  if (error) {
    const code = error instanceof ApiError ? error.code : "UNKNOWN";
    return (
      <div role="alert" className="flex max-w-md flex-col items-start gap-4">
        <CloudOff className="size-6 text-ink-2" aria-hidden />
        <p className="text-ink">{te.has(code) ? te(code) : te("UNKNOWN")}</p>
        <Button variant="outline" className="h-11" onClick={() => refetch()}>
          {tc("retry")}
        </Button>
      </div>
    );
  }

  if (isLoading || !user) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-5 w-72" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }
  return <>{children(user)}</>;
}
