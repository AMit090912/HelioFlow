"use client";

import { useState } from "react";

import { errorText } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useCloseLead, useUpgrade, type StaffLeadDetail } from "@/lib/staff";

const TERMINAL = new Set(["accepted", "converted", "closed_lost"]);

/** Upgrade a call to a visit, or close the lead. Both need a reason that goes on the record. */
export function LeadActions({ lead }: { lead: StaffLeadDetail }) {
  const upgrade = useUpgrade(lead.id);
  const close = useCloseLead(lead.id);
  const [open, setOpen] = useState<"upgrade" | "close" | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canUpgrade = lead.status === "call_pending";
  const canClose = !TERMINAL.has(lead.status);
  if (!canUpgrade && !canClose) return null;

  const submit = async () => {
    setError(null);
    try {
      await (open === "upgrade" ? upgrade : close).mutateAsync({ reason });
      setOpen(null);
      setReason("");
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err.code, err.message) : "Couldn't save. Try again.");
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {canUpgrade ? (
          <Button variant="outline" className="h-11" aria-expanded={open === "upgrade"} onClick={() => setOpen(open === "upgrade" ? null : "upgrade")}>
            Upgrade to survey visit
          </Button>
        ) : null}
        {canClose ? (
          <Button
            variant="ghost"
            className="h-11 text-ink-2"
            aria-expanded={open === "close"}
            onClick={() => setOpen(open === "close" ? null : "close")}
          >
            Close lead
          </Button>
        ) : null}
      </div>
      {open ? (
        <div className="space-y-2 rounded-xl border border-border bg-surface/60 p-3">
          <label htmlFor="action-reason" className="text-sm font-medium text-ink">
            {open === "upgrade" ? "Why does this lead deserve a visit?" : "Why is this lead closed?"}
          </label>
          <textarea
            id="action-reason"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-[0.9375rem]"
          />
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
          <div className="flex gap-2">
            <Button className="h-10" onClick={submit} disabled={upgrade.isPending || close.isPending}>
              {open === "upgrade" ? "Upgrade" : "Close lead"}
            </Button>
            <Button variant="ghost" className="h-10" onClick={() => setOpen(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
