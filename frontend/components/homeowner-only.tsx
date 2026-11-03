"use client";

import { useEffect, type ReactNode } from "react";

import { RequireSession } from "@/components/require-session";
import { useRouter } from "@/i18n/navigation";
import type { UserOut } from "@/lib/api";

function StaffGoesToInbox() {
  const router = useRouter();
  useEffect(() => router.replace("/staff/leads"), [router]);
  return null;
}

/** Homeowner screens: signed-out people go to sign-in, staff go to their inbox. */
export function HomeownerOnly({ children }: { children: (user: UserOut) => ReactNode }) {
  return (
    <RequireSession>{(user) => (user.role === "homeowner" ? children(user) : <StaffGoesToInbox />)}</RequireSession>
  );
}
