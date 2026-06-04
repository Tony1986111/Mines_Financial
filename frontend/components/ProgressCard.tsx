"use client";

import { useEffect, useState } from "react";

export type ProgressCardVariant = "status" | "tools" | "result" | "direct" | "fallback";

export interface ProgressCardData {
  id: string;
  status: "running" | "done";
  variant: ProgressCardVariant;
  text?: string;
  icon?: string;
  title?: string;
  bodyLines?: string[];
  tools?: { label: string; icon: string }[];
  expandBody?: string;
}

export default function ProgressCard({ card }: { card: ProgressCardData }) {
  const [visible, setVisible] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 30);
    return () => clearTimeout(t);
  }, []);

  const base =
    `rounded-xl px-3.5 py-2.5 text-xs leading-relaxed flex items-start gap-2.5 border transition-all duration-300 ${
      visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1"
    }`;

  if (card.status === "running") {
    return (
      <div className={`${base} relative overflow-hidden bg-[#1a4a8a]/[0.07] dark:bg-[#0d1c2e] border-[#b0c8e0]/40 dark:border-[#162840] text-[#1a4a8a] dark:text-[#7aade8]`}>
        <div className="shimmer-bar" />
        <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0 mt-0.5 animate-pulse ring-2 ring-blue-500/20" />
        <span className="relative">{card.text}</span>
      </div>
    );
  }

  if (card.variant === "direct") {
    return (
      <div className={`${base} bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/30 text-emerald-700 dark:text-emerald-400`}>
        <span className="shrink-0">💬</span>
        <span>{card.text}</span>
      </div>
    );
  }

  if (card.variant === "fallback") {
    return (
      <div className={`${base} bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/30 text-amber-700 dark:text-amber-400`}>
        <span>{card.text}</span>
      </div>
    );
  }

  if (card.variant === "tools") {
    return (
      <div className={`${base} flex-wrap bg-[#f4f8fd] dark:bg-[#0d1c2e] border-[#cddcea] dark:border-[#162840] text-[#0a1e38] dark:text-[#c4d8f0]`}>
        <span className="shrink-0 mt-0.5">⚙️</span>
        <div className="flex flex-wrap gap-x-1 items-center">
          <span className="text-[#7a9ab8] dark:text-[#3d5878] mr-1">Starting:</span>
          {card.tools?.map((tool, i) => (
            <span key={tool.label} className="font-semibold">
              {tool.icon}&nbsp;{tool.label}
              {i < (card.tools?.length ?? 0) - 1 && (
                <span className="text-[#7a9ab8] dark:text-[#3d5878] mx-1">+</span>
              )}
            </span>
          ))}
        </div>
      </div>
    );
  }

  // variant === "result"
  const isExpandable = !!card.expandBody;
  return (
    <div className={`${base} flex-col gap-1.5 bg-white dark:bg-[#0d1c2e] border-[#cddcea] dark:border-[#162840] shadow-sm`}>
      <div
        className={`flex items-center gap-2 font-semibold text-[#1a4a8a] dark:text-[#7aade8] ${isExpandable ? "cursor-pointer select-none" : ""}`}
        onClick={isExpandable ? () => setExpanded(e => !e) : undefined}
      >
        {card.icon && <span>{card.icon}</span>}
        <span className="flex-1">{card.title}</span>
        {isExpandable && (
          <span className="text-[10px] text-[#7a9ab8] dark:text-[#3d5878]">{expanded ? "▲" : "▼"}</span>
        )}
      </div>
      {card.bodyLines && card.bodyLines.length > 0 && (
        <div className="pl-6 flex flex-wrap gap-1.5">
          {card.bodyLines.map((line, i) => (
            <span
              key={i}
              className="inline-block bg-[#fef6e4] dark:bg-[#1a1004] border border-[#e8c86a] dark:border-[#3d2800] rounded px-2 py-0.5 text-[11px] font-mono font-semibold text-[#966000] dark:text-[#c4880c]"
            >
              {line}
            </span>
          ))}
        </div>
      )}
      {isExpandable && expanded && (
        <div className="pl-6 text-[11px] text-[#7a9ab8] dark:text-[#5a7898] leading-relaxed border-t border-[#e0eaf5] dark:border-[#1e3858] pt-1.5 mt-0.5 whitespace-pre-wrap">
          {card.expandBody}
        </div>
      )}
    </div>
  );
}
