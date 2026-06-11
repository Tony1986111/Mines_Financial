"use client";

import { useEffect } from "react";
import { parseVisionTable } from "@/lib/chatContent";
import type { SourceItem } from "@/types/chat";

interface SourceModalProps {
  source: SourceItem;
  index: number;
  onClose: () => void;
}

export default function SourceModal({
  source,
  index,
  onClose,
}: SourceModalProps) {
  const isTable = source.source_type === "vision";
  const parsed = isTable && source.full_content ? parseVisionTable(source.full_content) : null;

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
