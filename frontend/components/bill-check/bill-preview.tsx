"use client";

import { Maximize2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { previewUrl } from "@/lib/leads";

/**
 * The uploaded bill beside its values, so each number can be checked against the source.
 * Tapping it opens a full-size view on the same page (a native modal <dialog>: Esc, the ✕ button
 * or a click outside closes it, and focus returns to the bill), instead of leaving the page.
 * Served same-origin by the API (owner only, no-store); a plain <img> because next/image would
 * try to optimise a private, uncacheable response.
 */
export function BillPreview({ readingId }: { readingId: string }) {
  const t = useTranslations("billCheck.review");
  const [failed, setFailed] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  if (failed) return null;
  const src = previewUrl(readingId);

  return (
    <>
      <button
        type="button"
        onClick={() => dialog.current?.showModal()}
        aria-label={t("enlarge")}
        className="group relative block w-full cursor-zoom-in overflow-hidden rounded-2xl border border-border bg-background shadow-[0_18px_40px_-30px_rgba(1,46,43,0.45)]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={t("previewAlt")}
          className="max-h-[18rem] w-full object-contain object-top md:max-h-[40rem]"
          onError={() => setFailed(true)}
        />
        <span
          aria-hidden
          className="absolute right-3 top-3 flex size-9 items-center justify-center rounded-full bg-night/80 text-white opacity-90 transition-opacity group-hover:opacity-100"
        >
          <Maximize2 className="size-4" />
        </span>
      </button>

      <dialog
        ref={dialog}
        aria-label={t("previewAlt")}
        // A click on the backdrop lands on the <dialog> itself, not on its content.
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
        className="m-auto max-h-[94dvh] max-w-[94vw] overflow-visible bg-transparent p-0 backdrop:bg-night/85 backdrop:backdrop-blur-[2px]"
      >
        <div className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={t("previewAlt")} className="block max-h-[90dvh] max-w-[90vw] rounded-xl bg-white object-contain" />
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            aria-label={t("closePreview")}
            autoFocus
            className="absolute -right-3 -top-3 flex size-11 items-center justify-center rounded-full bg-white text-ink shadow-lg ring-1 ring-black/10 hover:bg-surface"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>
      </dialog>
    </>
  );
}
