"use client";

import Link from "next/link";
import { useState } from "react";
import { FolderOpen, Plus, AlertTriangle, CheckCircle2, Clock, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createWorkspace,
  listWorkspaces,
  type Workspace,
  type WorkspaceStatus,
} from "@/lib/api/workspaces";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Status display helpers
// ---------------------------------------------------------------------------

function StatusPip({ status }: { status: WorkspaceStatus }) {
  const base = "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium";
  if (status === "needs_review")
    return <span className={cn(base, "bg-amber-50 text-amber-700 ring-1 ring-amber-200")}><AlertTriangle className="h-3 w-3" />Needs Review</span>;
  if (status === "ready")
    return <span className={cn(base, "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200")}><CheckCircle2 className="h-3 w-3" />Ready</span>;
  if (status === "processing")
    return <span className={cn(base, "bg-blue-50 text-blue-700 ring-1 ring-blue-200")}><Loader2 className="h-3 w-3 animate-spin" />Processing</span>;
  if (status === "failed")
    return <span className={cn(base, "bg-red-50 text-red-700 ring-1 ring-red-200")}>Failed</span>;
  return <span className={cn(base, "bg-zinc-100 text-zinc-500 ring-1 ring-zinc-200")}><Clock className="h-3 w-3" />Pending</span>;
}

// ---------------------------------------------------------------------------
// Create workspace dialog (inline, no external dep)
// ---------------------------------------------------------------------------

function CreateWorkspaceForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [name, setName] = useState("");
  const [vertical, setVertical] = useState("cre");
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => createWorkspace({ name: name.trim(), vertical_id: vertical }),
    onSuccess: (ws) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      setOpen(false);
      setName("");
      onCreated(ws.id);
    },
  });

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="mr-1.5 h-4 w-4" />
        New Workspace
      </Button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-base font-semibold text-zinc-900">New Workspace</h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-zinc-700">Workspace name</label>
            <input
              autoFocus
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="e.g. Basingstoke Logistics — Q3 2025"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && name.trim() && mutation.mutate()}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-zinc-700">Vertical</label>
            <select
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              value={vertical}
              onChange={(e) => setVertical(e.target.value)}
            >
              <option value="cre">Commercial Real Estate</option>
              <option value="construction">Construction</option>
              <option value="insurance">Insurance</option>
              <option value="logistics">Logistics</option>
            </select>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            size="sm"
            disabled={!name.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
            Create
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workspace card
// ---------------------------------------------------------------------------

function WorkspaceCard({ ws }: { ws: Workspace }) {
  const created = new Date(ws.created_at).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <Link
      href={`/workspaces/${ws.id}`}
      className="group flex items-center justify-between rounded-xl border border-zinc-200/80 bg-white px-4 py-3.5 shadow-sm transition-all hover:border-zinc-300 hover:shadow-md"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-400 group-hover:bg-blue-50 group-hover:text-blue-500">
          <FolderOpen className="h-[18px] w-[18px]" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-zinc-900 group-hover:text-blue-600">{ws.name}</p>
          <p className="mt-0.5 text-[11px] text-zinc-400">{ws.vertical_id.toUpperCase()} · {created}</p>
        </div>
      </div>
      <div className="ml-4 flex shrink-0 items-center gap-3">
        <StatusPip status={ws.status} />
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function WorkspacesPage() {
  const { data: workspaces, isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => listWorkspaces(),
    refetchInterval: 5000,
  });
  const [, setCreatedId] = useState<string | null>(null);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6">
      <PageHeader
        kicker="Intelligence Layer"
        title="Workspaces"
        description="Upload document packs. The platform classifies, extracts, and validates across sources — surfacing issues before decisions are made."
        aside={
          <CreateWorkspaceForm onCreated={(id) => setCreatedId(id)} />
        }
      />

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[62px] w-full rounded-xl bg-zinc-100" />
          ))}
        </div>
      ) : !workspaces?.length ? (
        <EmptyState
          icon={FolderOpen}
          title="No workspaces yet"
          description="Create a workspace and upload your document pack to get started."
        />
      ) : (
        <div className="space-y-2">
          {workspaces.map((ws) => (
            <WorkspaceCard key={ws.id} ws={ws} />
          ))}
        </div>
      )}
    </div>
  );
}
