"use client";

import { useEffect, useId, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type GraphView = "workflow" | "studio" | "subgraph";

interface MermaidGraphModalProps {
  open: boolean;
  diagram: string | null;
  loading: boolean;
  error: string | null;
  isDark: boolean;
  onClose: () => void;
}

export default function MermaidGraphModal({
  open,
  diagram,
  loading,
  error,
  isDark,
  onClose,
}: MermaidGraphModalProps) {
  const rawId = useId();
  const renderId = `langgraph-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const [svg, setSvg] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const [view, setView] = useState<GraphView>("workflow");
  const [cacheBuster, setCacheBuster] = useState(Date.now());

  // Refresh cache-buster each time the modal opens so images are never stale.
  useEffect(() => {
    if (open) setCacheBuster(Date.now());
  }, [open]);

  const viewButtons: { id: GraphView; label: string }[] = [
    { id: "workflow", label: "Workflow" },
    { id: "studio", label: "Studio_Graph" },
    { id: "subgraph", label: "Subgraph" },
  ];

  useEffect(() => {
    if (!open || !diagram) return;

    let cancelled = false;
    const source = diagram;

    async function renderDiagram() {
      try {
        setRenderError(null);
        const palette = isDark
          ? {
              background: "#071424",
              nodeFill: "#10243d",
              nodeStroke: "#4f8fd8",
              text: "#d9ebff",
              startFill: "#0f2f27",
              startStroke: "#46c18b",
              endFill: "#27335f",
              endStroke: "#9aa8ff",
              endText: "#eef2ff",
              line: "#7ea6d8",
              edgeLabel: "#0b1b31",
            }
          : {
              background: "#f7fbff",
              nodeFill: "#eaf4ff",
              nodeStroke: "#4b83c6",
              text: "#17365d",
              startFill: "#e7f8f0",
              startStroke: "#2fa976",
              endFill: "#eef0ff",
              endStroke: "#6f7bdc",
              endText: "#27305f",
              line: "#5f85b3",
              edgeLabel: "#f7fbff",
            };
        const styledSource = `${source}
classDef default fill:${palette.nodeFill},stroke:${palette.nodeStroke},color:${palette.text},stroke-width:1.4px
classDef first fill:${palette.startFill},stroke:${palette.startStroke},color:${palette.text},stroke-width:1.6px
classDef last fill:${palette.endFill},stroke:${palette.endStroke},color:${palette.endText},stroke-width:1.6px
linkStyle default stroke:${palette.line},stroke-width:1.3px
`;
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          flowchart: {
            curve: "basis",
            htmlLabels: true,
            nodeSpacing: 34,
            padding: 12,
            rankSpacing: 40,
          },
          themeVariables: {
            background: palette.background,
            primaryColor: palette.nodeFill,
            primaryBorderColor: palette.nodeStroke,
            primaryTextColor: palette.text,
            lineColor: palette.line,
            edgeLabelBackground: palette.edgeLabel,
            fontFamily: "var(--font-syne), ui-sans-serif, system-ui, sans-serif",
            fontSize: "13px",
          },
        });
        const result = await mermaid.render(`${renderId}-${Date.now()}`, styledSource);
        if (!cancelled) setSvg(result.svg);
      } catch (err) {
        if (!cancelled) {
          setSvg("");
          setRenderError(err instanceof Error ? err.message : "Failed to render graph");
        }
      }
    }

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [diagram, isDark, open, renderId]);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-[#030810]/80 px-4 py-6 backdrop-blur-md">
      <div className="flex h-[min(820px,calc(100vh-48px))] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-[#162840] bg-white shadow-2xl shadow-black/40 dark:border-[#1e3858] dark:bg-[#091524]">
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-[#cddcea] dark:border-[#162840] px-5 bg-[#f4f8fd] dark:bg-[#091524]">
          <div className="min-w-0">
            <h2 className="text-sm font-bold tracking-tight text-[#0a1e38] dark:text-[#dce8f8]">
              LangGraph Workflow
            </h2>
            <p className="text-[10px] text-[#7a9ab8] dark:text-[#3d5878] font-mono">
              Workflow structure and graph exports
            </p>
          </div>
          <div className="ml-4 flex rounded-lg border border-[#cddcea] dark:border-[#162840] bg-[#eef4fb] dark:bg-[#060c14] p-0.5">
            {viewButtons.map((item) => (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                  view === item.id
                    ? "bg-[#1a4a8a] text-white shadow-sm dark:bg-[#1e5cba] dark:text-white"
                    : "text-[#7a9ab8] hover:bg-[#e8f0fa] hover:text-[#0a1e38] dark:text-[#3d5878] dark:hover:bg-[#0d1c2e] dark:hover:text-[#c4d8f0]"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button
            onClick={onClose}
            className="ml-auto flex h-7 w-7 items-center justify-center rounded-lg text-sm text-[#7a9ab8] transition-colors hover:bg-[#e8f0fa] hover:text-[#0a1e38] dark:text-[#3d5878] dark:hover:bg-[#0d1c2e] dark:hover:text-[#c4d8f0]"
            title="Close"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-auto bg-[#eef4fb] p-5 dark:bg-[#060c14]">
          {view === "workflow" && loading && (
            <div className="flex h-full items-center justify-center text-sm text-[#7a9ab8] dark:text-[#3d5878]">
              Loading LangGraph workflow...
            </div>
          )}

          {view === "workflow" && !loading && (error || renderError) && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300">
              {error ?? renderError}
            </div>
          )}

          {view === "workflow" && !loading && !error && !renderError && svg && (
            <div
              className="flex min-h-full min-w-[720px] items-center justify-center rounded-lg border border-[#cddcea] bg-[#f7fbff] p-6 shadow-sm dark:border-[#162840] dark:bg-[#071424] [&_.edgeLabel]:rounded [&_.nodeLabel]:text-[12px] [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:w-[860px] [&_svg]:max-w-full"
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          )}

          {view === "studio" && (
            <div className="flex min-h-full min-w-[720px] items-center justify-center rounded-lg border border-[#162840] bg-[#0d1c2e] p-5 shadow-sm dark:border-[#162840]">
              <img
                src={`${API_BASE}/assets/graph.png?v=${cacheBuster}`}
                alt="Studio graph"
                className="h-auto w-auto max-h-[476px] max-w-[70%] rounded object-contain"
              />
            </div>
          )}

          {view === "subgraph" && (
            <div className="flex min-h-full min-w-[720px] items-center justify-center rounded-lg border border-[#162840] bg-[#0d1c2e] p-5 shadow-sm dark:border-[#162840]">
              <img
                src={`${API_BASE}/assets/with_subgraph.png?v=${cacheBuster}`}
                alt="Graph with retrieval subgraph"
                className="h-auto w-auto max-h-[476px] max-w-[70%] rounded object-contain"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
