"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { previewUrl } from "@/lib/leads";

/**
 * The uploaded bill beside its values, so each number can be checked against the source.
 * Served same-origin by the API (owner only, no-store); a plain <img> because next/image would
 * try to optimise a private, uncacheable response.
 */
export function BillPreview({ readingId }: { readingId: string }) {
  const t = useTranslations("billCheck.review");
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <a
      href={previewUrl(readingId)}
      target="_blank"
      rel="noopener noreferrer"
      className="block overflow-hidden rounded-2xl border border-border bg-background shadow-[0_18px_40px_-30px_rgba(1,46,43,0.45)]"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={previewUrl(readingId)}
        alt={t("previewAlt")}
        className="max-h-[18rem] w-full object-contain object-top md:max-h-[40rem]"
        onError={() => setFailed(true)}
      />
    </a>
  );
}
