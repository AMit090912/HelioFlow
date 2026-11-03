"use client";

import { Camera, FileText, Loader2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { uploadBill, type Reading } from "@/lib/leads";
import { cn } from "@/lib/utils";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";
const TYPES = new Set(ACCEPT.split(","));
// Phone photos are often 4–8 MB; shrinking them first makes uploads on mobile data fast while
// keeping enough detail for the server's quality gate (short side ≥ 700 px, sharpness).
const COMPRESS_ABOVE = 1.5 * 1024 * 1024;

async function prepare(file: File): Promise<File> {
  if (file.type === "application/pdf" || file.size <= COMPRESS_ABOVE) return file;
  try {
    const { default: compress } = await import("browser-image-compression");
    const out = await compress(file, {
      maxSizeMB: 1.5,
      maxWidthOrHeight: 2600,
      initialQuality: 0.88,
      fileType: "image/jpeg",
      useWebWorker: true,
    });
    return new File([out], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file; // compression is an optimisation; the server checks the original just as well
  }
}

/**
 * The bill picker shared by the form's step 3 and the check-bill screen's re-upload panel.
 * Calls `onUploaded` with the new reading; the caller decides where to go next.
 */
export function BillUploader({
  leadId,
  onUploaded,
  submitLabel,
}: {
  leadId: string;
  onUploaded: (reading: Reading) => void;
  submitLabel?: string;
}) {
  const t = useTranslations("leadForm.bill");
  const te = useTranslations("errors");
  const pickRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "preparing" | "uploading">("idle");
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const busy = phase !== "idle";

  const choose = (picked: File | undefined | null) => {
    setError(null);
    if (!picked) return;
    if (!TYPES.has(picked.type)) {
      setFile(null);
      setError(te("FILE_TYPE_UNSUPPORTED"));
      return;
    }
    if (picked.size === 0) {
      setFile(null);
      setError(te("FILE_EMPTY"));
      return;
    }
    // Images over the limit may still compress below it; PDFs cannot.
    if (picked.type === "application/pdf" && picked.size > MAX_BYTES) {
      setFile(null);
      setError(te("FILE_TOO_LARGE"));
      return;
    }
    setFile(picked);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!busy) choose(e.dataTransfer.files?.[0]);
  };

  const submit = async () => {
    if (!file || busy) return;
    setError(null);
    setPhase("preparing");
    const ready = await prepare(file);
    if (ready.size > MAX_BYTES) {
      setPhase("idle");
      setError(te("FILE_TOO_LARGE"));
      return;
    }
    setPhase("uploading");
    setProgress(0);
    try {
      const reading = await uploadBill(leadId, ready, setProgress);
      onUploaded(reading);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "UNKNOWN";
      setError(te.has(code) ? te(code) : te("UNKNOWN"));
      setPhase("idle");
    }
  };

  return (
    <div className="space-y-5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-3xl border-2 border-dashed px-5 py-8 text-center transition-colors",
          dragging ? "border-teal bg-teal-wash/70" : "border-input bg-background",
        )}
      >
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileText className="size-9 text-teal" aria-hidden />
            <p className="max-w-full truncate font-medium text-ink">{file.name}</p>
            <p className="text-sm text-ink-2 tabular">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
            {!busy ? (
              <button
                type="button"
                className="mt-1 min-h-11 rounded-md px-3 text-sm font-medium text-teal underline-offset-4 hover:underline"
                onClick={() => pickRef.current?.click()}
              >
                {t("change")}
              </button>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <p className="hidden font-medium text-ink sm:block">{t("drop")}</p>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              {/* On phones the camera is the quickest way to a bill; desktop gets the file picker first. */}
              <Button type="button" size="lg" className="h-12 text-base sm:hidden" onClick={() => cameraRef.current?.click()}>
                <Camera className="size-5" aria-hidden />
                {t("camera")}
              </Button>
              <Button type="button" size="lg" variant="outline" className="h-12 text-base" onClick={() => pickRef.current?.click()}>
                <Upload className="size-5" aria-hidden />
                {t("pick")}
              </Button>
            </div>
            <p className="text-sm text-ink-2">{t("types")}</p>
          </div>
        )}
        <input
          ref={pickRef}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            choose(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            choose(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>

      {phase === "uploading" ? (
        <div aria-live="polite" className="space-y-2">
          <p className="text-sm text-ink-2 tabular">{t("uploading", { percent: Math.round(progress * 100) })}</p>
          <div
            className="h-2 overflow-hidden rounded-full bg-teal-wash"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
          >
            <div className="h-full rounded-full bg-teal transition-[width] duration-200" style={{ width: `${progress * 100}%` }} />
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Button type="button" size="lg" className="h-12 w-full text-base" disabled={!file || busy} onClick={submit}>
        {busy ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {phase === "preparing" ? t("preparing") : t("uploading", { percent: Math.round(progress * 100) })}
          </>
        ) : (
          (submitLabel ?? t("submit"))
        )}
      </Button>
    </div>
  );
}

/** The photo tips, shown beside the uploader. */
export function BillTips() {
  const t = useTranslations("leadForm.bill");
  return (
    <div className="rounded-2xl bg-surface p-4">
      <p className="font-semibold text-ink">{t("tipsTitle")}</p>
      <ul className="mt-2 space-y-1.5 text-[0.9375rem] text-ink-2">
        {(["flat", "light", "whole"] as const).map((k) => (
          <li key={k} className="flex gap-2">
            <span aria-hidden className="mt-2.5 size-1.5 shrink-0 rounded-full bg-gold" />
            {t(`tips.${k}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}
