"use client";

import { Check, Copy, Link2Off, RefreshCw } from "lucide-react";
import { useState } from "react";

import { projectError } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { statusUrl, useRegenerateLink, useRevokeLink, type ProjectDetail } from "@/lib/projects";

/**
 * The public status link (§12). The server keeps only a hash, so the full link is visible
 * once, right after it is made; afterwards staff can only regenerate (which kills the old one)
 * or revoke.
 */
export function StatusLinkBox({
  project,
  freshToken,
  locale,
}: {
  project: ProjectDetail;
  freshToken?: string | null;
  locale: string;
}) {
  const regenerate = useRegenerateLink(project.id);
  const revoke = useRevokeLink(project.id);
  const [token, setToken] = useState<string | null>(freshToken ?? null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const url = token ? statusUrl(token, locale) : null;

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy. Select the link and copy it by hand.");
    }
  };

  const doRegenerate = async () => {
    setError(null);
    try {
      const out = await regenerate.mutateAsync();
      setToken(out.status_token);
    } catch (err) {
      setError(err instanceof ApiError ? projectError(err.code, err.message) : "Couldn't make a new link.");
    }
  };

  const doRevoke = async () => {
    setError(null);
    try {
      await revoke.mutateAsync();
      setToken(null);
    } catch (err) {
      setError(err instanceof ApiError ? projectError(err.code, err.message) : "Couldn't turn off the link.");
    }
  };

  return (
    <div className="space-y-3">
      {url ? (
        <div className="rounded-xl border border-teal/40 bg-teal-wash/40 p-3">
          <p className="text-sm font-medium text-ink">Copy this link now: it won&apos;t be shown again.</p>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              readOnly
              value={url}
              onFocus={(e) => e.currentTarget.select()}
              aria-label="Status link"
              className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm tabular text-ink"
            />
            <Button type="button" className="h-10" onClick={copy}>
              {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-ink-2">
          {project.link.active
            ? "A link is active. For privacy only its fingerprint is stored; make a new one to share it again."
            : "No active link. Make one to share the project's progress."}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" className="h-10" onClick={doRegenerate} disabled={regenerate.isPending}>
          <RefreshCw className="size-4" aria-hidden />
          {project.link.active ? "Make a new link" : "Make a link"}
        </Button>
        {project.link.active ? (
          <Button type="button" variant="ghost" className="h-10 text-ink-2" onClick={doRevoke} disabled={revoke.isPending}>
            <Link2Off className="size-4" aria-hidden />
            Turn off link
          </Button>
        ) : null}
      </div>
      {project.link.active && !url ? (
        <p className="text-[0.8125rem] text-ink-2">Making a new link stops the old one working.</p>
      ) : null}
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
