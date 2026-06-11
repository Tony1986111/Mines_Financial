"use client";

import { useState } from "react";
import type { NodeDoneEvent } from "@/lib/api";

// ── StateViewer ───────────────────────────────────────────────────────────────

function StateValue({ value }: { value: unknown }) {
  const [open, setOpen] = useState(false);

  if (value === null || value === undefined) {
    return <span className="text-[#3d5878] italic">null</span>;
  }

  if (typeof value === "boolean") {
    return (
      <span className={value ? "text-emerald-500" : "text-rose-400"}>
        {String(value)}
      </span>
    );
  }

  if (typeof value === "number") {
    return <span className="text-amber-500 dark:text-amber-400">{value}</span>;
  }

  if (typeof value === "string") {
    const display = value.length > 120 ? value.slice(0, 120) + "…" : value;
    return (
      <span
        className="text-emerald-700 dark:text-emerald-400 cursor-pointer break-all"
        title={value}
        onClick={() => setOpen(o => !o)}
      >
        {open ? `"${value}"` : `"${display}"`}
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[#3d5878]">[]</span>;
    return (
      <span>
        <button
          onClick={() => setOpen(o => !o)}
          className="text-[#1a4a8a] dark:text-[#7aade8] hover:underline font-mono text-xs"
        >
          {open ? "▼" : "▶"} [{value.length}]
        </button>
        {open && (
          <div className="ml-4 mt-1 border-l border-[#162840] pl-2 space-y-0.5">
            {value.map((item, i) => (
              <div key={i} className="flex gap-1.5 text-xs">
                <span className="text-[#3d5878] shrink-0">{i}:</span>
                <StateValue value={item} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-[#3d5878]">{"{}"}</span>;
    return (
      <span>
        <button
          onClick={() => setOpen(o => !o)}
          className="text-[#1a4a8a] dark:text-[#7aade8] hover:underline font-mono text-xs"
        >
          {open ? "▼" : "▶"} {"{"}…{"}"}
        </button>
        {open && (
          <div className="ml-4 mt-1 border-l border-[#162840] pl-2 space-y-0.5">
            {entries.map(([k, v]) => (
              <div key={k} className="flex gap-1.5 text-xs">
                <span className="text-[#7a9ab8] shrink-0 font-mono">{k}:</span>
                <StateValue value={v} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  return <span className="text-[#0a1e38] dark:text-[#c4d8f0] text-xs">{String(value)}</span>;
}

function StateViewer({ state }: { state: Record<string, unknown> }) {
  const entries = Object.entries(state).filter(([k]) => !k.startsWith("_"));
  return (
    <div className="mt-2 space-y-1 text-xs font-mono bg-[#eef4fb] dark:bg-[#060c14] border border-[#cddcea] dark:border-[#162840] rounded-lg p-3 max-h-72 overflow-y-auto">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2 items-start">
          <span className="text-[#1a4a8a] dark:text-[#7aade8] shrink-0 font-semibold">{k}:</span>
          <StateValue value={v} />
        </div>
      ))}
    </div>
  );
}

// ── Custom detail renderers ───────────────────────────────────────────────────

function QueryRewriteDetails({ state }: { state: Record<string, unknown> }) {
  const cqs = (state.company_queries as Array<{ company: string; query: string }> | undefined) ?? [];
  if (cqs.length === 0) return <p className="text-[10px] italic text-[#7a9ab8] dark:text-[#3d5878] mt-2">pending for company queries</p>;
  return (
    <div className="mt-2 space-y-1 text-xs font-mono bg-[#eef4fb] dark:bg-[#060c14] border border-[#cddcea] dark:border-[#162840] rounded-lg p-3">
      {cqs.map(({ company, query }) => (
        <div key={company} className="flex gap-2 items-start">
          <span className="text-[#1a4a8a] dark:text-[#7aade8] font-semibold shrink-0 w-10">{company}:</span>
          <span className="text-[#0a1e38] dark:text-[#c4d8f0] break-all leading-relaxed">{query}</span>
        </div>
      ))}
    </div>
  );
}

function RetrieveCompanyDetails({ state }: { state: Record<string, unknown> }) {
  const cs = (state.company_status as Record<string, boolean> | undefined) ?? {};
  const entries = Object.entries(cs);
  if (entries.length === 0) return <p className="text-[10px] italic text-[#7a9ab8] dark:text-[#3d5878] mt-2">pending for company name</p>;
  return (
    <div className="mt-2 text-xs font-mono bg-[#eef4fb] dark:bg-[#060c14] border border-[#cddcea] dark:border-[#162840] rounded-lg p-3 space-y-1">
      {entries.map(([company, found]) => (
        <div key={company} className="flex items-center gap-2">
          <span className={found ? "text-emerald-600 dark:text-emerald-400" : "text-rose-500 dark:text-rose-400"}>{found ? "✓" : "✗"}</span>
          <span className="text-[#0a1e38] dark:text-[#c4d8f0]">{company}</span>
        </div>
      ))}
    </div>
  );
}

// ── Node status indicator ─────────────────────────────────────────────────────

const SUBGRAPH_NODES = new Set([
  "query_rewrite", "retrieve_company", "grade_docs", "synthesize", "grade_answer",
]);

// Nodes that carry state but should not be expandable.
const NO_EXPAND_NODES = new Set(["synthesize"]);

const NODE_LABELS: Record<string, string> = {
  compress_context: "Compress Context",
  memory: "Memory",
  retrieve_decision: "Retrieve Decision",
  clarify: "Clarify",
  retrieval_agent: "Retrieval Agent",
  news_agent: "News Agent",
  calculator_agent: "Calculator Agent",
  aggregate: "Aggregate",
  guardrails: "Guardrails",
  fallback: "Fallback",
  answer: "Answer",
  // inner retrieval subgraph nodes
  query_rewrite: "↳ Query Rewrite",
  retrieve_company: "↳ Retrieve Company",
  grade_docs: "↳ Grade Docs",
  synthesize: "↳ Synthesise",
  grade_answer: "↳ Grade Answer",
};

interface NodeRowProps {
  node: string;
  status: "done" | "running";
  state?: Record<string, unknown>;
}

function NodeRow({ node, status, state }: NodeRowProps) {
  const [expanded, setExpanded] = useState(false);
  let label = NODE_LABELS[node] ?? node;
  if (node === "retrieval_agent") {
    label = status === "running" ? "Retrieval Agent starts" : "Retrieval Agent ends";
  }
  const isSubgraph = SUBGRAPH_NODES.has(node);

  // compress_context: show compressed flag
  let compressedBadge: boolean | null = null;
  if (node === "compress_context" && status === "done" && state) {
    if (typeof state.compressed === "boolean") compressedBadge = state.compressed;
  }

  // retrieval_agent: show company count
  let retrievalCount: number | null = null;
  if (node === "retrieval_agent" && status === "done" && state) {
    const cs = (state.retrieval_result as { company_status?: Record<string, unknown> } | undefined)?.company_status;
    if (cs && typeof cs === "object") retrievalCount = Object.keys(cs).length;
  }

  // grade_docs: show graded doc count + pass/fail
  let gradeDocsBadge: string | null = null;
  if (node === "grade_docs" && status === "done" && state) {
    const count = (state.graded_docs as unknown[] | undefined)?.length ?? 0;
    gradeDocsBadge = `${count} doc${count !== 1 ? "s" : ""} ${state.grade === "pass" ? "✓" : "✗"}`;
  }

  // grade_answer: show grounded status
  let groundedBadge: { label: string; cls: string } | null = null;
  if (node === "grade_answer" && status === "done" && state) {
    const g = state.grounded as string | undefined;
    if (g === "yes")      groundedBadge = { label: "verified",   cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400" };
    else if (g === "partial") groundedBadge = { label: "partial",    cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400" };
    else if (g === "no")  groundedBadge = { label: "unverified", cls: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400" };
  }

  const isRetrievalStarts = node === "retrieval_agent" && status === "running";
  const canExpand = !!state && !NO_EXPAND_NODES.has(node);

  return (
    <div>
      <button
        onClick={() => canExpand && setExpanded(o => !o)}
        disabled={!canExpand}
        className={`w-full flex items-center gap-2.5 rounded-lg text-left transition-colors ${
          isSubgraph ? "px-7 py-2" : "px-3 py-2"
        } ${
          canExpand ? "hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] cursor-pointer" : "cursor-default"
        }`}
      >
        {/* Status dot */}
        {isRetrievalStarts ? (
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 ring-1 ring-emerald-500/20" />
        ) : status === "running" ? (
          <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0 animate-pulse ring-2 ring-blue-500/20" />
        ) : isSubgraph ? (
          <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0 ring-1 ring-blue-400/20" />
        ) : (
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 ring-1 ring-emerald-500/20" />
        )}

        <span className={`text-xs font-medium flex-1 ${
          status === "running"
            ? "text-blue-600 dark:text-blue-400"
            : isSubgraph
            ? "text-blue-700 dark:text-blue-300"
            : "text-[#0a1e38] dark:text-[#c4d8f0]"
        }`}>
          {label}
        </span>

        {compressedBadge !== null && (
          <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${
            compressedBadge
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
              : "bg-[#e8f0fa] text-[#7a9ab8] dark:bg-[#0d1c2e] dark:text-[#3d5878]"
          }`}>
            {compressedBadge ? "true" : "false"}
          </span>
        )}

        {retrievalCount !== null && (
          <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400">
            ({retrievalCount})
          </span>
        )}

        {gradeDocsBadge !== null && (
          <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400">
            {gradeDocsBadge}
          </span>
        )}

        {groundedBadge !== null && (
          <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${groundedBadge.cls}`}>
            {groundedBadge.label}
          </span>
        )}

        {canExpand && (
          <span className="text-[10px] text-[#7a9ab8] dark:text-[#3d5878]">
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </button>

      {expanded && canExpand && (
        <div className="px-3 pb-2">
          {node === "query_rewrite" ? (
            <QueryRewriteDetails state={state!} />
          ) : node === "retrieve_company" ? (
            <RetrieveCompanyDetails state={state!} />
          ) : (
            <StateViewer state={state!} />
          )}
        </div>
      )}
    </div>
  );
}

// ── GraphPanel ────────────────────────────────────────────────────────────────

export interface GraphNodeEvent {
  node: string;
  status: "done" | "running";
  state?: Record<string, unknown>;
}

interface GraphPanelProps {
  events: GraphNodeEvent[];
  visible: boolean;
  width: number;
  onToggle: () => void;
}

export default function GraphPanel({ events, visible, width, onToggle }: GraphPanelProps) {
  return (
    <aside
      className="shrink-0 flex flex-col border-l border-[#cddcea] dark:border-[#162840] bg-[#f4f8fd] dark:bg-[#091524]"
      style={{ width: visible ? `min(${width}px, 100vw)` : 36 }}
    >
      {/* Toggle button */}
      <div className="h-12 flex items-center border-b border-[#cddcea] dark:border-[#162840] shrink-0 px-2">
        <button
          onClick={onToggle}
          title={visible ? "Hide graph panel" : "Show graph panel"}
          className="w-6 h-6 flex items-center justify-center rounded text-[#7a9ab8] dark:text-[#3d5878] hover:text-[#1a4a8a] dark:hover:text-[#7aade8] hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] transition-colors text-xs"
        >
          {visible ? "›" : "‹"}
        </button>
        {visible && (
          <>
            <span className="ml-2 text-xs font-bold tracking-wide text-[#0a1e38] dark:text-[#c4d8f0]">
              Graph Progress
            </span>
            <div className="ml-auto flex items-center gap-1">
              <a
                href="https://github.com/Tony1986111/Mines_Financial"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Open GitHub repository"
                title="GitHub repository"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#0a1e38] bg-[#0a1e38] text-white shadow-sm shadow-[#0a1e38]/20 transition-all hover:-translate-y-0.5 hover:border-[#1a4a8a] hover:bg-[#1a4a8a] dark:border-[#5a8fc8]/50 dark:bg-[#16375c] dark:text-[#dce8f8] dark:hover:border-[#7eb3e8] dark:hover:bg-[#1f4f82]"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
                  <path d="M12 .5C5.73.5.75 5.58.75 11.95c0 5.07 3.29 9.37 7.86 10.9.57.11.78-.25.78-.56 0-.27-.01-1.17-.02-2.12-3.2.71-3.88-1.39-3.88-1.39-.52-1.35-1.28-1.71-1.28-1.71-1.05-.73.08-.72.08-.72 1.16.08 1.77 1.21 1.77 1.21 1.03 1.79 2.71 1.27 3.37.97.1-.76.4-1.27.73-1.56-2.55-.3-5.24-1.3-5.24-5.73 0-1.27.45-2.3 1.18-3.11-.12-.3-.51-1.52.12-3.07 0 0 .97-.31 3.16 1.19a10.8 10.8 0 0 1 5.75 0c2.19-1.5 3.16-1.19 3.16-1.19.63 1.55.24 2.77.12 3.07.74.81 1.18 1.84 1.18 3.11 0 4.45-2.69 5.43-5.26 5.72.42.37.79 1.08.79 2.18 0 1.57-.01 2.83-.01 3.22 0 .31.21.68.79.56 4.57-1.53 7.85-5.83 7.85-10.9C23.25 5.58 18.27.5 12 .5Z" />
                </svg>
              </a>
              <a
                href="https://tonyiscoding.melailab.com/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Open Tony's portfolio website"
                title="Tony's portfolio"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#0a1e38] bg-[#0a1e38] text-white shadow-sm shadow-[#0a1e38]/20 transition-all hover:-translate-y-0.5 hover:border-[#1a4a8a] hover:bg-[#1a4a8a] dark:border-[#5a8fc8]/50 dark:bg-[#16375c] dark:text-[#dce8f8] dark:hover:border-[#7eb3e8] dark:hover:bg-[#1f4f82]"
              >
                <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="5" width="16" height="14" rx="2.5" />
                  <path d="M9 5V3.8A1.8 1.8 0 0 1 10.8 2h2.4A1.8 1.8 0 0 1 15 3.8V5" />
                  <circle cx="9" cy="11" r="2" />
                  <path d="M6.7 16c.55-1.15 1.3-1.7 2.3-1.7s1.75.55 2.3 1.7" />
                  <path d="M14 10h3.5M14 14h3.5" />
                </svg>
              </a>
            </div>
          </>
        )}
      </div>

      {visible && (
        <div className="flex-1 overflow-y-auto py-2">
          {events.length === 0 ? (
            <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] italic text-center mt-6 px-4">
              Graph progress will appear here when you send a message.
            </p>
          ) : (
            <div className="space-y-0.5 px-1">
              {events.map((e, i) =>
                e.node === "__turn__" ? (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 my-1">
                    <div className="flex-1 h-px bg-[#cddcea] dark:bg-[#162840]" />
                    <span className="text-[9px] text-[#94b0cc] dark:text-[#3d5878] font-mono truncate max-w-[130px]" title={String(e.state?.query ?? "")}>
                      {String(e.state?.query ?? "")}
                    </span>
                    <div className="flex-1 h-px bg-[#cddcea] dark:bg-[#162840]" />
                  </div>
                ) : (
                  <NodeRow
                    key={`${e.node}-${i}`}
                    node={e.node}
                    status={e.status}
                    state={e.state}
                  />
                )
              )}
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
