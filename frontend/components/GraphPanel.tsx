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
  const entries = Object.entries(state);
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

// ── Node status indicator ─────────────────────────────────────────────────────

const NODE_LABELS: Record<string, string> = {
  compress_context: "Compress Context",
  memory: "Memory",
  retrieve_decision: "Retrieve Decision",
  dynamic_tool_selector: "Tool Selector",
  clarify: "Clarify",
  retrieval_agent: "Retrieval Agent",
  news_agent: "News Agent",
  calculator_agent: "Calculator Agent",
  aggregate: "Aggregate",
  guardrails: "Guardrails",
  fallback: "Fallback",
  answer: "Answer",
};

interface NodeRowProps {
  node: string;
  status: "done" | "running";
  state?: Record<string, unknown>;
}

function NodeRow({ node, status, state }: NodeRowProps) {
  const [expanded, setExpanded] = useState(false);
  const label = NODE_LABELS[node] ?? node;

  // For compress_context, read the explicit `compressed` flag set by the node.
  let compressedBadge: boolean | null = null;
  if (node === "compress_context" && status === "done" && state) {
    if (typeof state.compressed === "boolean") {
      compressedBadge = state.compressed;
    }
  }

  // For retrieval_agent, count how many companies were retrieved in parallel.
  let retrievalCount: number | null = null;
  if (node === "retrieval_agent" && status === "done" && state) {
    const result = (state.retrieval_result as { company_status?: Record<string, unknown> } | undefined);
    const cs = result?.company_status;
    if (cs && typeof cs === "object") retrievalCount = Object.keys(cs).length;
  }

  return (
    <div>
      <button
        onClick={() => state && setExpanded(o => !o)}
        disabled={!state}
        className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors ${
          state
            ? "hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] cursor-pointer"
            : "cursor-default"
        }`}
      >
        {/* Status dot */}
        {status === "running" ? (
          <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0 animate-pulse ring-2 ring-blue-500/20" />
        ) : (
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 ring-1 ring-emerald-500/20" />
        )}

        <span className={`text-xs font-medium flex-1 ${
          status === "running"
            ? "text-blue-600 dark:text-blue-400"
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

        {state && (
          <span className="text-[10px] text-[#7a9ab8] dark:text-[#3d5878]">
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </button>

      {expanded && state && (
        <div className="px-3 pb-2">
          <StateViewer state={state} />
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
          <span className="ml-2 text-xs font-bold tracking-wide text-[#0a1e38] dark:text-[#c4d8f0]">
            Graph Progress
          </span>
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
