"use client";

import { SUGGESTIONS } from "@/lib/suggestions";

interface ChatEmptyStateProps {
  onSelectSuggestion: (text: string) => void;
}

export default function ChatEmptyState({ onSelectSuggestion }: ChatEmptyStateProps) {
  return (
    <div className="min-h-full flex flex-col items-center justify-center gap-4 py-3 md:gap-8 md:py-0">
      <div className="text-center">
        <p className="text-3xl mb-2 md:text-4xl md:mb-4">⛏️</p>
        <p className="font-bold text-base tracking-tight text-[#0a1e38] dark:text-[#dce8f8] md:text-lg">Ask about ASX mining financials</p>
        <p className="text-xs text-[#7a9ab8] dark:text-[#3d5878] mt-1 md:text-sm md:mt-1.5">Revenue · Profit · EBITDA · Capex · Dividends</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 md:gap-4 w-full max-w-3xl">
        {SUGGESTIONS.map(group => (
          <div key={group.category} className="flex flex-col gap-1 md:gap-1.5">
            <p className="flex items-center gap-1.5 text-[10px] font-semibold text-[#5a7a9a] uppercase tracking-wider mb-0.5 px-1 md:text-[11px]">
              <span>{group.icon}</span>
              {group.category}
            </p>
            {group.items.map(s => (
              <button
                key={s}
                onClick={() => onSelectSuggestion(s)}
                className="text-left text-xs text-[#1a4a8a] dark:text-[#7aade8] bg-white dark:bg-[#0d1c2e] hover:bg-[#e8f0fa] dark:hover:bg-[#111e30] border border-[#cddcea] dark:border-[#162840] hover:border-[#b0c8e0] dark:hover:border-[#1e3858] rounded-lg px-3 py-2 transition-all shadow-sm hover:shadow-md md:rounded-xl md:px-3.5 md:py-2.5 md:text-sm"
              >
                <span className="flex items-center gap-2">
                  <span className="text-[#c4880c] text-xs font-bold leading-none shrink-0">→</span>
                  <span className="leading-snug">{s}</span>
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
