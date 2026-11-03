"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { SignInSunrise } from "@/components/illustrations/sign-in-story";
import { SpotAccount, SpotHome, SpotUpload } from "@/components/illustrations/spot";
import {
  clearDraft,
  loadHome,
  loadHomeDone,
  loadLeadId,
  saveHomeDone,
  saveLeadId,
  type HomeDraft,
} from "@/components/lead-form/draft";
import { StepAccount } from "@/components/lead-form/step-account";
import { BillTips, BillUploader } from "@/components/lead-form/step-bill";
import { StepHome } from "@/components/lead-form/step-home";
import { SunPath } from "@/components/lead-form/sun-path";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { updateLead, useLead, useMyLeads } from "@/lib/leads";
import { homeFor, useSession } from "@/lib/use-session";

type Phase = "home" | "account" | "bill";

function isComplete(home: Partial<HomeDraft> | null): home is HomeDraft {
  return !!home && (["ownership", "property_type", "roof_type", "roof_area_sqft", "monthly_bill", "pincode"] as const).every((k) => !!home[k]);
}

const noop = () => () => {};

/** sessionStorage only exists in the browser, so the flow renders after hydration. */
export function GetSolarFlow() {
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  return mounted ? <Flow /> : <div className="min-h-dvh bg-surface" />;
}

function Flow() {
  const t = useTranslations("leadForm");
  const tc = useTranslations("common");
  const router = useRouter();
  const { user, isLoading } = useSession();
  const searchParams = useSearchParams();

  // Restored from sessionStorage. Safe in initialisers: GetSolarPage only mounts this on the client.
  const [home, setHome] = useState<Partial<HomeDraft> | null>(loadHome);
  // ?lead=<id> comes from the dashboard's "Continue": upload for that lead, never create another.
  const [leadId, setLeadId] = useState<string | null>(() => {
    const fromLink = searchParams.get("lead");
    if (fromLink && /^[0-9a-f-]{36}$/i.test(fromLink)) {
      saveLeadId(fromLink);
      return fromLink;
    }
    return loadLeadId();
  });
  // ?step=home with a lead: "Edit home details" from the check-bill screen.
  const [phase, setPhase] = useState<Phase>(() =>
    leadId
      ? searchParams.get("step") === "home"
        ? "home"
        : "bill"
      : loadHomeDone() && isComplete(home)
        ? "account"
        : "home",
  );

  // The step list is fixed by whether the person arrived signed in, so it doesn't jump from three
  // steps to two the moment the account is created in step 2.
  const [arrivedSignedIn, setArrivedSignedIn] = useState<boolean | null>(null);
  if (!isLoading && arrivedSignedIn === null) setArrivedSignedIn(user !== null); // once, on first answer
  const shortFlow = arrivedSignedIn === true;

  const isStaff = !!user && user.role !== "homeowner";
  useEffect(() => {
    if (isStaff) router.replace(homeFor(user));
  }, [isStaff, user, router]);

  // A signed-in homeowner with an unfinished enquiry continues it instead of starting a second
  // lead (the dashboard only shows the newest one).
  const checkOpen = !!user && user.role === "homeowner" && !leadId;
  const { data: myLeads, isPending: myLeadsPending } = useMyLeads(checkOpen);
  const openLead = checkOpen ? (myLeads?.find((l) => !l.next_action) ?? null) : null;
  const activeLeadId = leadId ?? openLead?.id ?? null;
  const activePhase: Phase = !leadId && openLead ? "bill" : phase;

  // Focus moves to the new step's heading after a step change (not on first load).
  const [firstPhase] = useState(phase);
  const focusHeading = activePhase !== firstPhase;

  const steps = shortFlow ? [t("steps.home"), t("steps.bill")] : [t("steps.home"), t("steps.account"), t("steps.bill")];
  const current = activePhase === "home" ? 0 : shortFlow ? 1 : activePhase === "account" ? 1 : 2;
  const stepLabel = t("stepOf", { current: current + 1, total: steps.length });

  const ready = !isLoading && arrivedSignedIn !== null && !(checkOpen && myLeadsPending);

  let body: ReactNode;
  if (!ready) {
    body = (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-28 w-full rounded-2xl" />
      </div>
    );
  } else if (isStaff) {
    body = <p className="text-ink-2" role="status">{t("staffRedirect")}</p>;
  } else if (activePhase === "home" && activeLeadId) {
    // Editing the details of a lead that already exists (Back from the bill step).
    body = (
      <StepSection illustration={<SpotHome className="w-24" />} title={t("steps.home")} focus={focusHeading}>
        <EditHome leadId={activeLeadId} onFinished={() => setPhase("bill")} />
      </StepSection>
    );
  } else if (activePhase === "home") {
    body = (
      <StepSection illustration={<SpotHome className="w-24" />} title={t("steps.home")} focus={focusHeading}>
        <StepHome
          initial={home}
          onDone={(values) => {
            setHome(values);
            saveHomeDone(true);
            setPhase("account");
          }}
        />
      </StepSection>
    );
  } else if (activePhase === "account" && isComplete(home)) {
    body = (
      <StepSection
        focus={focusHeading}
        illustration={<SpotAccount className="w-28" />}
        title={user ? t("steps.bill") : t("account.title")}
        subtitle={user ? undefined : t("account.subtitle")}
      >
        <StepAccount
          user={user}
          home={home}
          onBack={() => {
            saveHomeDone(false);
            setPhase("home");
          }}
          onCreated={(lead) => {
            saveLeadId(lead.id);
            setLeadId(lead.id);
            setPhase("bill");
          }}
        />
      </StepSection>
    );
  } else if (activePhase === "bill" && activeLeadId) {
    body = (
      <BillStep
        leadId={activeLeadId}
        focus={focusHeading}
        signInToResume={arrivedSignedIn === true}
        onUploaded={(readingId) => {
          clearDraft();
          router.push(`/my/bill/${readingId}`);
        }}
        onBack={() => {
          // Keep editing the same lead, even when it was found as the open one.
          saveLeadId(activeLeadId);
          setLeadId(activeLeadId);
          setPhase("home");
        }}
        onLost={() => {
          // The saved lead belongs to someone else or no longer exists: start again cleanly.
          clearDraft();
          setHome(null);
          setLeadId(null);
          setPhase("home");
        }}
      />
    );
  } else {
    body = null;
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(340px,0.85fr)_1.4fr]">
      {/* The sky: brand, promise and the sun's path across the three steps. */}
      {/* Desktop: pinned to the viewport, so the brand and the step path stay in view while the
          form scrolls beside it. */}
      <aside className="relative overflow-hidden bg-night text-white lg:sticky lg:top-0 lg:h-dvh lg:self-start">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-gold/10 blur-2xl" />
        <div className="relative flex h-full flex-col gap-6 px-4 pb-8 pt-3 sm:px-6 lg:gap-12 lg:px-10 lg:pb-12 lg:pt-8">
          <div className="flex h-14 items-center justify-between lg:h-auto">
            <Link href={homeFor(user)} aria-label={tc("appName")} className="rounded-md">
              <Logo tone="dark" />
            </Link>
            <LanguageSwitcher className="text-white/80 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white lg:hidden" />
          </div>
          <div className="max-w-sm">
            <h1 className="font-display text-[1.75rem] font-semibold leading-[1.15] lg:text-[2.25rem]">{t("title")}</h1>
            <p className="mt-2 text-white/75">{t("subtitle")}</p>
          </div>
          <SunPath steps={steps} current={current} label={stepLabel} className="max-w-sm lg:mt-4" />
          <p className="mt-auto hidden max-w-xs text-sm text-white/55 lg:block">{t("bill.privacy")}</p>
          {/* The brand sunrise closes the column, so the pinned panel never looks empty. */}
          <div className="relative -mx-10 -mb-12 hidden h-52 lg:block">
            <SignInSunrise className="absolute inset-0 size-full" />
          </div>
        </div>
      </aside>

      <div className="flex flex-col bg-surface">
        <div className="hidden h-[4.5rem] items-center justify-between px-10 lg:flex">
          <p className="text-sm text-ink-2" aria-hidden>
            {stepLabel}
          </p>
          <LanguageSwitcher />
        </div>
        <main className="flex-1 px-4 pb-16 pt-6 sm:px-6 lg:px-10 lg:pt-2">
          <div className="mx-auto w-full max-w-2xl rounded-3xl border border-border bg-background p-5 shadow-[0_24px_60px_-36px_rgba(1,46,43,0.35)] sm:p-8">
            {/* Keyed by step so each step mounts fresh (and its heading takes focus). */}
            <div key={activePhase}>{body}</div>
          </div>
        </main>
      </div>
    </div>
  );
}

function StepSection({
  illustration,
  title,
  subtitle,
  focus = false,
  children,
}: {
  illustration: ReactNode;
  title: string;
  subtitle?: string;
  focus?: boolean;
  children: ReactNode;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focus) headingRef.current?.focus();
  }, [focus]);
  return (
    <section>
      <div className="mb-7 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-5">
        <div className="shrink-0">{illustration}</div>
        <div>
          <h2 ref={headingRef} tabIndex={-1} className="font-display text-[1.5rem] font-semibold text-ink outline-none sm:text-[1.75rem]">
            {title}
          </h2>
          {subtitle ? <p className="mt-1 text-ink-2">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function BillStep({
  leadId,
  focus,
  signInToResume,
  onUploaded,
  onBack,
  onLost,
}: {
  leadId: string;
  focus: boolean;
  signInToResume: boolean;
  onUploaded: (readingId: string) => void;
  onBack: () => void;
  onLost: () => void;
}) {
  const t = useTranslations("leadForm");
  const router = useRouter();
  const { data: lead, error } = useLead(leadId);

  const status = error instanceof ApiError ? error.status : null;
  // 401 for someone who arrived signed out means the saved lead was left by a previous person on
  // this device (signed out since): start fresh rather than loop through sign-in.
  const lost = status === 404 || status === 422 || (status === 401 && !signInToResume);
  const alreadyUploaded = lead?.latest_reading ?? null;

  useEffect(() => {
    if (lost) onLost();
  }, [lost, onLost]);

  // Signed out meanwhile (session expired): sign in and come back to this same lead.
  useEffect(() => {
    if (status === 401 && signInToResume) router.replace({ pathname: "/sign-in", query: { next: "/get-solar" } });
  }, [status, signInToResume, router]);

  // A reload after the upload already went through: continue on the check-bill screen.
  useEffect(() => {
    if (alreadyUploaded) {
      clearDraft();
      router.replace(`/my/bill/${alreadyUploaded.id}`);
    }
  }, [alreadyUploaded, router]);

  return (
    <StepSection illustration={<SpotUpload className="w-28" />} title={t("bill.title")} subtitle={t("bill.subtitle")} focus={focus}>
      {lead ? <p className="-mt-3 mb-5 text-sm text-ink-2">{t("bill.leadSaved", { code: lead.code })}</p> : null}
      <div className="grid gap-6 md:grid-cols-[1fr_15rem]">
        <div className="space-y-4">
          <BillUploader leadId={leadId} onUploaded={(reading) => onUploaded(reading.id)} />
          <Button type="button" variant="ghost" className="h-12 px-0 text-base text-ink-2 sm:px-4" onClick={onBack}>
            <ArrowLeft className="size-4" aria-hidden />
            {t("editDetails")}
          </Button>
        </div>
        <div className="space-y-4">
          <BillTips />
          <p className="text-sm text-ink-2 lg:hidden">{t("bill.privacy")}</p>
        </div>
      </div>
    </StepSection>
  );
}

/** Step 1 again, pre-filled from the saved lead; saving updates that same lead. */
function EditHome({ leadId, onFinished }: { leadId: string; onFinished: () => void }) {
  const t = useTranslations("leadForm");
  const client = useQueryClient();
  const { data: lead } = useLead(leadId);
  if (!lead) return <Skeleton className="h-64 w-full rounded-2xl" />;
  const initial: HomeDraft = {
    ownership: lead.ownership,
    property_type: lead.property_type,
    roof_type: lead.roof_type,
    roof_area_sqft: lead.roof_area_sqft,
    monthly_bill: lead.declared_monthly_bill,
    pincode: lead.pincode,
  };
  return (
    <StepHome
      key={lead.id}
      initial={initial}
      submitLabel={t("saveAndContinue")}
      onBack={onFinished}
      onDone={async (values) => {
        await updateLead(leadId, values);
        await client.invalidateQueries({ queryKey: ["leads"] });
        onFinished();
      }}
    />
  );
}
