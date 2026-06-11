"use client";

import { useEffect, useState } from "react";
import ProgressCard, { type ProgressCardData } from "./ProgressCard";
import BarChart from "./BarChart";
import type { ChartSpec } from "@/lib/api";

export interface SourceItem {
  label: string;
  preview: string;
  source_type?: string;
  full_content?: string;
}

export interface Message {
  role: "user" | "assistant" | "system" | "progress";
  content: string;
  cards?: ProgressCardData[];
  chartData?: ChartSpec[];
  sources?: SourceItem[];
  confidence?: string;
  unsupportedClaims?: Array<{ claim: string; basis: string }>;
}

// Strip the trailing "Sources:\n[N] ..." block from final_answer text —
// we render sources as interactive buttons instead.
const _SOURCES_TAIL_RE = /\n\nSources:\n[\s\S]*$/;
function stripSourcesSection(text: string): string {
  return text.replace(_SOURCES_TAIL_RE, "");
}

// Parse a vision (table) chunk into structured rows for HTML table rendering.
// Content format from table_to_text():
//   Title: ...
//   Source: ... | Page: ...
//   Headers: col1 | col2
//   row1val1 | row1val2
function parseVisionTable(content: string): {
  title: string;
  headers: string[][];
  rows: string[][];
} {
  let headers: string[][] = [];
  let rows: string[][] = [];
  let title = "";

  for (const line of content.split("\n")) {
    const t = line.trim();
    if (t.startsWith("Title: ")) {
      title = t.slice(7);
    } else if (t.startsWith("Source: ") || t === "") {
      // skip metadata / blank lines
    } else if (t.startsWith("Headers: ")) {
      headers.push(t.slice(9).split(" | "));
    } else if (t.includes(" | ")) {
      rows.push(t.split(" | "));
    } else if (t) {
      rows.push([t]);
    }
  }

  if (headers.length > 0 && rows.length > 0) {
    const maxDataCols = Math.max(...rows.map(r => r.length));
    const maxHeaderCols = Math.max(...headers.map(h => h.length));

    // Case A: data rows have more columns than headers → vision model dropped
    // the leading empty header cell. Prepend empty strings to each header row.
    if (maxDataCols > maxHeaderCols) {
      headers = headers.map(h => {
        const diff = maxDataCols - h.length;
        return diff > 0 ? [...Array(diff).fill(""), ...h] : h;
      });
    }

    // Case B: headers have exactly 1 more column than data rows, AND all
    // significant data rows are consistently short → data rows are missing
    // their first (row-label) cell. Prepend empty string to each.
    if (maxHeaderCols - maxDataCols === 1) {
      const significant = rows.filter(r => r.length > 1);
      if (significant.length > 0 && significant.every(r => r.length === maxDataCols)) {
        rows = rows.map(r => r.length > 1 ? ["", ...r] : r);
      }
    }
  }

  return { title, headers, rows };
}

// ── Inline citation rendering ─────────────────────────────────────────────────

const _SPLIT_RE = /(```[\s\S]*?```|\{\{chart:[^}]+\}\}|<sup class="citation"[^>]*>\[[^\]]+\]<\/sup>)/g;
const _CHART_RE = /^\{\{chart:(.+)\}\}$/;
const _SUP_RE   = /^<sup class="citation"([^>]*)>(\[[^\]]+\])<\/sup>$/;

function renderContent(
  text: string,
  chartData?: ChartSpec[],
  sources?: SourceItem[],
) {
  const chartMap = new Map<string, ChartSpec>();
  if (chartData) {
    for (const c of chartData) {
      chartMap.set(c.title.split(" (")[0], c);
    }
  }

  const parts = text.split(_SPLIT_RE);
  return parts.map((part, i) => {
    if (part.startsWith("```")) {
      const code = part.replace(/^```[^\n]*\n?/, "").replace(/```$/, "");
      return (
        <pre key={i} className="mt-2 mb-1 bg-[#060c14] dark:bg-[#030810] rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre border border-[#162840] text-[#8ab8e8]">
          {code}
        </pre>
      );
    }

    const chartMatch = part.match(_CHART_RE);
    if (chartMatch) {
      const spec = chartMap.get(chartMatch[1]);
      return spec ? <BarChart key={i} spec={spec} /> : null;
    }

    const supMatch = part.match(_SUP_RE);
    if (supMatch) {
      const numText = supMatch[2];
      const allNums = numText.slice(1, -1)
        .split(",")
        .map(s => parseInt(s.trim(), 10))
        .filter(n => !isNaN(n) && n >= 1)
        .sort((a, b) => a - b);

      const sortedText = "[" + allNums.join(",") + "]";
      const srcs = sources
        ? allNums.map(n => ({ n, src: sources[n - 1] })).filter(({ src }) => src !== undefined)
        : [];

      if (srcs.length > 0) {
        return (
          <span key={i} className="relative inline-block group/cite">
            <sup className="text-[0.7em] font-bold text-[#7eb3e8] align-super leading-none ml-0.5 cursor-help underline decoration-dotted decoration-[#7eb3e8]/50">
              {sortedText}
            </sup>
            <div className="absolute bottom-full left-1/2 mb-2 w-[min(20rem,calc(100vw-2rem))] -translate-x-1/2 p-3 bg-[#091524] border border-[#162840] rounded-xl text-xs shadow-xl shadow-black/30 opacity-0 group-hover/cite:opacity-100 transition-opacity pointer-events-none z-50 whitespace-normal md:left-0 md:w-80 md:translate-x-0">
              {srcs.map(({ n, src }, idx) => (
                <div key={n} className={idx < srcs.length - 1 ? "mb-2 pb-2 border-b border-[#1e3858]" : ""}>
                  <p className="font-semibold text-[#7eb3e8] mb-1 leading-snug flex items-center gap-1.5">
                    <span className="text-[#c4880c] mr-1">[{n}]</span>
                    <span className="flex-1">{src.label}</span>
                    {src.source_type && (
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0 ${
                        src.source_type === "vision"
                          ? "bg-violet-500/15 text-violet-400"
                          : "bg-sky-500/15 text-sky-400"
                      }`}>
                        {src.source_type === "vision" ? "table" : "text"}
                      </span>
                    )}
                  </p>
                  {src.preview && (
                    <p className="text-[#7a9ab8] leading-relaxed line-clamp-3">{src.preview}</p>
                  )}
                </div>
              ))}
            </div>
          </span>
        );
      }
      return (
        <sup key={i} className="text-[0.7em] font-bold text-[#7eb3e8] align-super leading-none ml-0.5">
          {sortedText}
        </sup>
      );
    }

    return <span key={i} className="whitespace-pre-wrap">{part}</span>;
  });
}

// ── Source modal ──────────────────────────────────────────────────────────────

function SourceModal({
  source,
  index,
  onClose,
}: {
  source: SourceItem;
  index: number;
  onClose: () => void;
}) {
  const isTable = source.source_type === "vision";
  const parsed  = isTable && source.full_content ? parseVisionTable(source.full_content) : null;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-2 md:p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[calc(100dvh-1rem)] w-full max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-2xl border border-[#1e3858] bg-[#0d1c2e] shadow-2xl shadow-black/60 md:w-fit md:max-w-[90vw] md:max-h-[80vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center gap-2.5 border-b border-[#1e3858] px-3 py-3.5 shrink-0 md:flex-nowrap md:gap-3 md:px-5">
          <span className="text-[#c4880c] font-bold text-sm">[{index}]</span>
          <span className="min-w-0 flex-1 text-[#c4d8f0] text-sm font-medium leading-snug break-words">{source.label}</span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider shrink-0 ${
            isTable
              ? "bg-violet-500/15 text-violet-400 border border-violet-500/20"
              : "bg-sky-500/15 text-sky-400 border border-sky-500/20"
          }`}>
            {isTable ? "table" : "text"}
          </span>
          <button
            onClick={onClose}
            className="ml-1 w-6 h-6 flex items-center justify-center rounded-md text-[#5a7a9a] hover:text-[#c4d8f0] hover:bg-[#162840] transition-colors text-lg leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="overflow-auto p-3 flex-1 md:p-5">
          {!source.full_content ? (
            <p className="text-[#5a7a9a] text-sm italic">内容不可用</p>
          ) : isTable && parsed ? (
            <div className="overflow-x-auto">
              {parsed.title && (
                <p className="text-[#7eb3e8] font-semibold text-sm mb-3">{parsed.title}</p>
              )}
              <table className="w-full text-xs border-collapse">
                {parsed.headers.length > 0 && (
                  <thead>
                    {parsed.headers.map((hrow, ri) => (
                      <tr key={ri}>
                        {hrow.map((cell, ci) => (
                          <th
                            key={ci}
                            className="text-left px-3 py-1.5 text-[#7eb3e8] font-semibold bg-[#091524] border border-[#1e3858] whitespace-nowrap"
                          >
                            {cell}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                )}
                <tbody>
                  {parsed.rows.map((row, ri) => (
                    <tr key={ri} className={ri % 2 === 0 ? "bg-[#0a1828]" : "bg-[#091220]"}>
                      {row.map((cell, ci) => (
                        <td
                          key={ci}
                          className="px-3 py-1.5 text-[#a8c4e0] border border-[#162840] whitespace-nowrap"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <pre className="text-xs text-[#a8c4e0] whitespace-pre-wrap break-words leading-relaxed font-mono">
              {source.full_content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ChatMessage({
  message,
  typewriter = false,
}: {
  message: Message;
  typewriter?: boolean;
}) {
  const [displayed, setDisplayed]       = useState(typewriter ? "" : message.content);
  const [cursorVisible, setCursorVisible] = useState(typewriter);
  const [activeSourceIdx, setActiveSourceIdx] = useState<number | null>(null);

  useEffect(() => {
    if (!typewriter) {
      setDisplayed(message.content);
      setCursorVisible(false);
      return;
    }
    setDisplayed("");
    setCursorVisible(true);
    let i = 0;
    const text = message.content;
    const id = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        setCursorVisible(false);
      }
    }, 12);
    return () => clearInterval(id);
  }, [message.content, typewriter]);

  // ── Progress cards ─────────────────────────────────────────────────────────
  if (message.role === "progress") {
    const cards = message.cards ?? [];
    if (cards.length === 0) return null;
    return (
      <div className="flex gap-2.5 mb-3 md:gap-3">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#1e5cba] to-[#1a4a8a] shrink-0 flex items-center justify-center text-[10px] font-bold text-white mt-0.5 ring-1 ring-white/10">
          AI
        </div>
        <div className="min-w-0 flex-1 flex flex-col gap-2">
          {cards.map(card => (
            <ProgressCard key={card.id} card={card} />
          ))}
        </div>
      </div>
    );
  }

  // ── System message ─────────────────────────────────────────────────────────
  if (message.role === "system") {
    return (
      <div className="flex justify-center my-3">
        <span className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10 border border-amber-200 dark:border-amber-400/20 rounded-full px-3 py-1 font-medium">
          {message.content}
        </span>
      </div>
    );
  }

  // ── User / Assistant bubble ────────────────────────────────────────────────
  const isUser    = message.role === "user";
  const sources   = message.sources ?? [];
  const cleanText = stripSourcesSection(displayed);

  return (
    <>
      <div className={`flex gap-2.5 mb-4 md:gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold mt-0.5 ring-1 ring-white/10 ${
          isUser
            ? "bg-[#1a4a8a] text-white"
            : "bg-gradient-to-br from-[#1e5cba] to-[#1a4a8a] text-white"
        }`}>
          {isUser ? "U" : "AI"}
        </div>

        <div className={`min-w-0 max-w-[calc(100%-2.375rem)] rounded-2xl px-3.5 py-3 text-sm leading-relaxed [overflow-wrap:anywhere] md:max-w-[75%] md:px-4 ${
          isUser
            ? "bg-gradient-to-b from-[#1e5cba] to-[#1a4a8a] text-white rounded-tr-sm shadow-sm shadow-[#1a4a8a]/20"
            : "bg-white dark:bg-[#0d1c2e] text-[#0a1e38] dark:text-[#c4d8f0] border border-[#cddcea] dark:border-[#162840] rounded-tl-sm shadow-sm dark:shadow-none"
        }`}>
          {/* Confidence badge */}
          {!isUser && message.confidence && (
            <div className={`text-[11px] font-semibold mb-2.5 pb-2 border-b ${
              message.confidence === "high"
                ? "text-emerald-600 dark:text-emerald-400 border-emerald-500/15"
                : message.confidence === "medium"
                ? "text-amber-600 dark:text-amber-400 border-amber-500/15"
                : "text-rose-600 dark:text-rose-400 border-rose-500/15"
            }`}>
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  message.confidence === "high" ? "bg-emerald-500 dark:bg-emerald-400"
                  : message.confidence === "medium" ? "bg-amber-500 dark:bg-amber-400"
                  : "bg-rose-500 dark:bg-rose-400"
                }`} />
                {message.confidence === "high"
                  ? "High Confidence — All facts verified against retrieved documents"
                  : message.confidence === "medium"
                  ? "Medium Confidence — Some claims could not be fully verified"
                  : "Low Confidence — Please cross-check with original annual reports"}
              </div>
              {message.confidence !== "high" && message.unsupportedClaims && message.unsupportedClaims.length > 0 && (
                <div className="mt-1.5 ml-3 font-normal opacity-80 flex flex-col gap-0.5">
                  <span className="font-semibold">Unverified:</span>
                  {message.unsupportedClaims.map((c, i) => {
                    const basisLabel: Record<string, string> = { calculation: "calculated from report data", interpolation: "estimated from report data", general_knowledge: "not found in reports" };
                    return (
                      <div key={i} className="flex gap-1.5">
                        <span className="shrink-0 font-semibold">{i + 1}.</span>
                        <span>
                          {c.claim}{" "}
                          <span className="opacity-60 text-[10px]">({basisLabel[c.basis] ?? c.basis})</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Main content */}
          {renderContent(cleanText, message.chartData, sources)}
          {cursorVisible && (
            <span className="inline-block w-0.5 h-3.5 bg-[#7eb3e8] ml-0.5 align-middle animate-blink" />
          )}

          {/* Sources bar */}
          {!isUser && sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-[#162840] dark:border-[#1e3858]">
              <p className="text-[10px] font-semibold text-[#5a7a9a] uppercase tracking-wider mb-2">
                Sources
              </p>
              <div className="flex flex-wrap gap-1.5">
                {sources.map((src, idx) => {
                  const isTable = src.source_type === "vision";
                  return (
                    <button
                      key={idx}
                      onClick={() => setActiveSourceIdx(idx)}
                      className="w-full md:w-auto flex min-w-0 items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs transition-colors bg-[#091524] border-[#1e3858] text-[#7a9ab8] hover:border-[#7eb3e8]/40 hover:text-[#a8c4e0] hover:bg-[#0f2035]"
                    >
                      <span className="text-[#c4880c] font-bold shrink-0">[{idx + 1}]</span>
                      <span className="min-w-0 flex-1 md:flex-none md:max-w-[180px] truncate">{src.label}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0 ${
                        isTable
                          ? "bg-violet-500/15 text-violet-400"
                          : "bg-sky-500/15 text-sky-400"
                      }`}>
                        {isTable ? "table" : "text"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Source detail modal */}
      {activeSourceIdx !== null && sources[activeSourceIdx] && (
        <SourceModal
          source={sources[activeSourceIdx]}
          index={activeSourceIdx + 1}
          onClose={() => setActiveSourceIdx(null)}
        />
      )}
    </>
  );
}
