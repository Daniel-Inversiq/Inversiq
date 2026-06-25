"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Lightbulb,
  Loader2,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
  Info,
  TrendingUp,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getWorkspace,
  pollWorkspaceStatus,
  registerDocument,
  resolveFlag,
  triggerProcessing,
  type WorkspaceDocument,
  type WorkspaceFlag,
  type WorkspaceStatus,
} from "@/lib/api/workspaces";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DOC_TYPE_LABELS: Record<string, string> = {
  information_memorandum: "Information Memorandum",
  rent_roll: "Rent Roll",
  tdd_report: "TDD Report",
  valuation_report: "Valuation Report",
  lease_agreement: "Lease Agreement",
  loan_termsheet: "Loan Term Sheet",
  financial_statements: "Financial Statements",
  epc_certificate: "EPC Certificate",
  site_plan: "Site Plan",
  other: "Other",
};

function docTypeLabel(t: string | null): string {
  if (!t) return "Classifying…";
  return DOC_TYPE_LABELS[t] ?? t.replace(/_/g, " ");
}

const STATUS_STEPS = ["uploaded", "classifying", "extracting", "extracted", "validated"];

function docStatusLabel(s: string): string {
  return (
    {
      uploaded: "Queued",
      classifying: "Classifying…",
      extracting: "Extracting…",
      extracted: "Extracted",
      validated: "Validated",
      failed: "Failed",
    }[s] ?? s
  );
}

function confPct(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const n = parseFloat(raw);
  return isNaN(n) ? null : Math.round(n * 100);
}

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    high: "bg-red-50 text-red-700 ring-1 ring-red-200",
    medium: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
    low: "bg-zinc-100 text-zinc-500 ring-1 ring-zinc-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        map[severity] ?? map.low,
      )}
    >
      {severity}
    </span>
  );
}

function WorkspaceStatusBadge({ status }: { status: WorkspaceStatus }) {
  if (status === "needs_review")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-200">
        <AlertTriangle className="h-3.5 w-3.5" />
        Needs Review
      </span>
    );
  if (status === "ready")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Ready
      </span>
    );
  if (status === "processing")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-200">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Processing
      </span>
    );
  if (status === "failed")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200">
        Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-500 ring-1 ring-zinc-200">
      Pending
    </span>
  );
}

// ---------------------------------------------------------------------------
// Metrics strip
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "amber" | "green" | "blue" | "red";
}) {
  const colors: Record<string, string> = {
    amber: "text-amber-600",
    green: "text-emerald-600",
    blue: "text-blue-600",
    red: "text-red-600",
  };
  return (
    <div className="rounded-xl border border-zinc-100 bg-white px-4 py-3.5 shadow-sm">
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold tabular-nums", accent ? colors[accent] : "text-zinc-900")}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[11px] text-zinc-400">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Document row — live status feed
// ---------------------------------------------------------------------------

function DocRow({
  doc,
}: {
  doc:
    | WorkspaceDocument
    | Pick<WorkspaceDocument, "id" | "filename" | "doc_type" | "status" | "classification_confidence">;
}) {
  const steps = STATUS_STEPS;
  const currentIdx = steps.indexOf(doc.status);
  const isFailed = doc.status === "failed";
  const isDone = doc.status === "validated" || doc.status === "extracted";
  const conf = confPct("classification_confidence" in doc ? doc.classification_confidence : null);

  return (
    <div className="flex items-start gap-4 rounded-lg border border-zinc-100 bg-white px-4 py-3 shadow-sm">
      <div
        className={cn(
          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          isFailed
            ? "bg-red-50 text-red-400"
            : isDone
              ? "bg-emerald-50 text-emerald-500"
              : "bg-blue-50 text-blue-400",
        )}
      >
        {isFailed ? (
          <X className="h-4 w-4" />
        ) : isDone ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-sm font-medium text-zinc-900">{doc.filename}</p>
          {conf !== null && <span className="shrink-0 text-[11px] text-zinc-400">{conf}% confidence</span>}
        </div>
        <div className="mt-1 flex items-center gap-3">
          {doc.doc_type && (
            <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-600">
              {docTypeLabel(doc.doc_type)}
            </span>
          )}
          <span
            className={cn(
              "text-[11px]",
              isFailed ? "text-red-500" : isDone ? "text-emerald-600 font-medium" : "text-zinc-400",
            )}
          >
            {docStatusLabel(doc.status)}
          </span>
        </div>
        {!isFailed && !isDone && (
          <div className="mt-2 flex gap-1">
            {steps.map((step, i) => (
              <div
                key={step}
                className={cn(
                  "h-0.5 flex-1 rounded-full transition-colors duration-500",
                  i <= currentIdx ? "bg-blue-400" : "bg-zinc-100",
                )}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flag review panel
// ---------------------------------------------------------------------------

function FlagPanel({
  flag,
  workspaceId,
  onResolved,
}: {
  flag: WorkspaceFlag;
  workspaceId: string;
  onResolved: () => void;
}) {
  const [note, setNote] = useState("");
  const [value, setValue] = useState("");
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (action: "resolve" | "escalate") =>
      resolveFlag(workspaceId, flag.id, action, { resolution_note: note, resolution_value: value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace-status", workspaceId] });
      qc.invalidateQueries({ queryKey: ["workspace", workspaceId] });
      onResolved();
    },
  });

  const sources =
    (flag.conflict_data?.sources as Array<{ doc: string; value: unknown; label?: string }>) ?? [];
  const reasoning = flag.conflict_data?.reasoning as string | undefined;
  const suggestedResolution = flag.conflict_data?.suggested_resolution as string | undefined;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity={flag.severity} />
          <span className="text-[11px] text-zinc-400">{flag.flag_type.replace(/_/g, " ")}</span>
        </div>
        <h3 className="mt-2 text-sm font-semibold text-zinc-900">{flag.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-zinc-600">{flag.detail}</p>
      </div>

      {/* Source comparison */}
      {sources.length > 0 && (
        <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
            Source comparison
          </p>
          <div className="space-y-2">
            {sources.map((src, i) => (
              <div key={i} className="flex items-start justify-between gap-3 text-sm">
                <span className="min-w-0 flex-1 text-zinc-500">
                  {src.doc}
                  {src.label ? <span className="ml-1 text-zinc-400 text-[11px]">({src.label})</span> : null}
                </span>
                <span className="shrink-0 font-mono font-semibold text-zinc-900">
                  {typeof src.value === "number" ? src.value.toLocaleString() : String(src.value ?? "—")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI reasoning */}
      {reasoning && (
        <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-blue-500" />
            <p className="text-[11px] font-semibold uppercase tracking-wide text-blue-600">AI Reasoning</p>
          </div>
          <p className="text-[12px] leading-relaxed text-blue-900">{reasoning}</p>
        </div>
      )}

      {/* Suggested resolution */}
      {suggestedResolution && (
        <div className="rounded-lg border border-amber-100 bg-amber-50/60 p-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <Lightbulb className="h-3.5 w-3.5 text-amber-600" />
            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">
              Suggested Resolution
            </p>
          </div>
          <p className="text-[12px] leading-relaxed text-amber-900">{suggestedResolution}</p>
        </div>
      )}

      {/* Resolution form */}
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600">Accepted value (optional)</label>
          <input
            className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
            placeholder="Enter the agreed value…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600">Decision note</label>
          <textarea
            className="w-full resize-none rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
            rows={2}
            placeholder="Add context for the audit trail…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          size="sm"
          className="flex-1"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate("resolve")}
        >
          {mutation.isPending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
          )}
          Mark Resolved
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="flex-1"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate("escalate")}
        >
          Escalate to IC
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload drop zone
// ---------------------------------------------------------------------------

function UploadZone({
  workspaceId,
  onUploaded,
}: {
  workspaceId: string;
  onUploaded: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const names = Array.from(files).map((f) => f.name);
      setUploading(names);
      try {
        for (const file of Array.from(files)) {
          await registerDocument(workspaceId, file.name);
        }
        qc.invalidateQueries({ queryKey: ["workspace-status", workspaceId] });
        qc.invalidateQueries({ queryKey: ["workspace", workspaceId] });
        onUploaded();
      } finally {
        setUploading([]);
      }
    },
    [workspaceId, qc, onUploaded],
  );

  return (
    <div
      className={cn(
        "relative cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors",
        dragging
          ? "border-blue-400 bg-blue-50/50"
          : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50/50",
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        className="sr-only"
        accept=".pdf,.xlsx,.xls,.doc,.docx"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {uploading.length > 0 ? (
        <div className="space-y-1">
          <Loader2 className="mx-auto h-5 w-5 animate-spin text-blue-400" />
          <p className="text-sm text-zinc-500">Registering {uploading.length} file(s)…</p>
        </div>
      ) : (
        <div className="space-y-1">
          <Upload className="mx-auto h-5 w-5 text-zinc-300" />
          <p className="text-sm font-medium text-zinc-600">Drop additional documents or click to browse</p>
          <p className="text-xs text-zinc-400">PDF, Excel, Word — IM, Rent Roll, TDD, Valuation, Lease</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ready banner
// ---------------------------------------------------------------------------

function ReadyBanner() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3.5">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100">
        <CheckCircle2 className="h-5 w-5 text-emerald-600" />
      </div>
      <div>
        <p className="text-sm font-semibold text-emerald-900">All issues resolved — workspace is ready</p>
        <p className="text-xs text-emerald-700">
          Document pack has been validated and all flags cleared. Safe to proceed to IC paper.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function WorkspaceDetailPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = use(params);
  const qc = useQueryClient();
  const [selectedFlagId, setSelectedFlagId] = useState<number | null>(null);

  const { data: workspace, isLoading } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => getWorkspace(workspaceId),
  });

  const { data: statusData } = useQuery({
    queryKey: ["workspace-status", workspaceId],
    queryFn: () => pollWorkspaceStatus(workspaceId),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "processing" || s === "pending" ? 2000 : false;
    },
    staleTime: 0,
  });

  const processMutation = useMutation({
    mutationFn: () => triggerProcessing(workspaceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace-status", workspaceId] });
      qc.invalidateQueries({ queryKey: ["workspace", workspaceId] });
    },
  });

  const status = statusData?.status ?? workspace?.status ?? "pending";
  const docs = statusData?.documents ?? workspace?.documents ?? [];
  const flags = statusData?.flags ?? workspace?.flags ?? [];
  const openFlags = flags.filter((f) => f.status === "open");
  const resolvedFlags = flags.filter((f) => f.status !== "open");

  const selectedFlag = flags.find((f) => f.id === selectedFlagId) ?? null;

  const isProcessing = status === "processing";
  const hasDocs = docs.length > 0;
  const canProcess = hasDocs && status === "pending";
  const isReady = status === "ready";

  // Derived metrics
  const validatedCount = docs.filter((d) => d.status === "validated" || d.status === "extracted").length;
  const overallConf = confPct(statusData?.overall_confidence ?? workspace?.overall_confidence ?? null);
  // Analyst time saved: each validated doc saves ~3h of manual review
  const hoursSaved = validatedCount * 3;

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6">
        <Skeleton className="h-8 w-64 rounded-lg bg-zinc-100" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl bg-zinc-100" />
          ))}
        </div>
        <Skeleton className="h-40 w-full rounded-xl bg-zinc-100" />
      </div>
    );
  }

  if (!workspace) return null;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6">
      {/* Back */}
      <Link
        href="/workspaces"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-600"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Workspaces
      </Link>

      {/* Header */}
      <PageHeader
        kicker={workspace.vertical_id.toUpperCase()}
        title={workspace.name}
        aside={
          <div className="flex items-center gap-3">
            <WorkspaceStatusBadge status={status} />
            {canProcess && (
              <Button
                size="sm"
                onClick={() => processMutation.mutate()}
                disabled={processMutation.isPending}
              >
                {processMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
                )}
                Start Analysis
              </Button>
            )}
          </div>
        }
      />

      {/* Metrics strip */}
      {(isProcessing || status === "needs_review" || status === "ready") && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard
            label="Confidence"
            value={overallConf !== null ? `${overallConf}%` : "—"}
            sub="Weighted avg. extraction"
            accent={overallConf !== null && overallConf >= 80 ? "green" : "amber"}
          />
          <MetricCard
            label="Documents"
            value={`${validatedCount}/${docs.length}`}
            sub="Validated"
            accent={validatedCount === docs.length ? "green" : "blue"}
          />
          <MetricCard
            label="Open Issues"
            value={String(openFlags.length)}
            sub={openFlags.length === 0 ? "All clear" : `${flags.filter(f => f.severity === "high" && f.status === "open").length} high severity`}
            accent={openFlags.length === 0 ? "green" : openFlags.some((f) => f.severity === "high") ? "red" : "amber"}
          />
          <MetricCard
            label="Time Saved"
            value={`~${hoursSaved}h`}
            sub="vs. manual review"
            accent="green"
          />
        </div>
      )}

      {/* Ready banner */}
      {isReady && <ReadyBanner />}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Left: documents + upload */}
        <div className="space-y-4 lg:col-span-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-700">
              Documents
              {docs.length > 0 && <span className="ml-1.5 text-zinc-400">({docs.length})</span>}
            </h2>
            {isProcessing && (
              <span className="flex items-center gap-1.5 text-[11px] text-blue-500">
                <Loader2 className="h-3 w-3 animate-spin" />
                Live
              </span>
            )}
          </div>

          {docs.length > 0 && (
            <div className="space-y-2">
              {docs.map((doc) => (
                <DocRow key={doc.id} doc={doc} />
              ))}
            </div>
          )}

          {/* Processing note */}
          {isProcessing && (
            <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2.5 text-sm text-blue-700">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Classifying and extracting — typically 20–60 seconds per document.
            </div>
          )}

          {/* Upload zone */}
          {(status === "pending" || status === "needs_review" || status === "ready") && (
            <UploadZone
              workspaceId={workspaceId}
              onUploaded={() => {
                qc.invalidateQueries({ queryKey: ["workspace-status", workspaceId] });
                qc.invalidateQueries({ queryKey: ["workspace", workspaceId] });
              }}
            />
          )}

          {/* Extracted summary */}
          {workspace.extracted_summary && Object.keys(workspace.extracted_summary).length > 0 && (
            <div className="rounded-xl border border-zinc-100 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <TrendingUp className="h-3.5 w-3.5 text-zinc-400" />
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Extracted Intelligence
                </h3>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                {Object.entries(workspace.extracted_summary)
                  .slice(0, 14)
                  .map(([k, v]) => (
                    <div key={k} className="min-w-0">
                      <dt className="text-[11px] text-zinc-400">{k.replace(/_/g, " ")}</dt>
                      <dd className="mt-0.5 truncate text-sm font-semibold text-zinc-900">
                        {typeof v === "number" ? v.toLocaleString() : String(v ?? "—")}
                      </dd>
                    </div>
                  ))}
              </dl>
            </div>
          )}
        </div>

        {/* Right: flags */}
        <div className="space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-700">
              Issues
              {openFlags.length > 0 && (
                <span className="ml-1.5 rounded-full bg-red-100 px-1.5 py-0.5 text-[11px] font-semibold text-red-600">
                  {openFlags.length} open
                </span>
              )}
            </h2>
          </div>

          {flags.length === 0 && !isProcessing && (
            <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center">
              <Info className="mx-auto mb-2 h-5 w-5 text-zinc-300" />
              <p className="text-sm text-zinc-400">
                {status === "pending"
                  ? "Issues will appear here after analysis runs."
                  : "No issues detected."}
              </p>
            </div>
          )}

          {isProcessing && flags.length === 0 && (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl bg-zinc-100" />
              ))}
            </div>
          )}

          {/* Open flags */}
          {openFlags.length > 0 && (
            <div className="space-y-2">
              {openFlags.map((flag) => (
                <button
                  key={flag.id}
                  onClick={() => setSelectedFlagId(selectedFlagId === flag.id ? null : flag.id)}
                  className={cn(
                    "w-full rounded-xl border px-4 py-3 text-left shadow-sm transition-all",
                    selectedFlagId === flag.id
                      ? "border-blue-200 bg-blue-50/50 shadow-blue-100/50"
                      : flag.severity === "high"
                        ? "border-red-100 bg-white hover:border-red-200 hover:shadow-md"
                        : "border-amber-100 bg-white hover:border-amber-200 hover:shadow-md",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={flag.severity} />
                      </div>
                      <p className="mt-1.5 text-sm font-semibold text-zinc-900">{flag.title}</p>
                      <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-zinc-500">
                        {flag.detail}
                      </p>
                    </div>
                    <ChevronRight
                      className={cn(
                        "mt-1 h-4 w-4 shrink-0 text-zinc-300 transition-transform",
                        selectedFlagId === flag.id && "rotate-90",
                      )}
                    />
                  </div>

                  {selectedFlagId === flag.id && (
                    <div
                      className="mt-4 border-t border-zinc-100 pt-4"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <FlagPanel
                        flag={flag}
                        workspaceId={workspaceId}
                        onResolved={() => setSelectedFlagId(null)}
                      />
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Resolved flags */}
          {resolvedFlags.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Resolved</p>
              {resolvedFlags.map((flag) => (
                <div
                  key={flag.id}
                  className="flex items-start gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2.5"
                >
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-zinc-600">{flag.title}</p>
                    {flag.resolution_note && (
                      <p className="mt-0.5 text-[11px] text-zinc-400">{flag.resolution_note}</p>
                    )}
                    <p className="mt-0.5 text-[11px] text-zinc-400">
                      {flag.resolved_by} ·{" "}
                      {flag.resolved_at ? new Date(flag.resolved_at).toLocaleTimeString() : ""}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
