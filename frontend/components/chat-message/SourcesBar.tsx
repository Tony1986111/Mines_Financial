import type { SourceItem } from "@/types/chat";

interface SourcesBarProps {
  sources: SourceItem[];
  onSelectSource: (index: number) => void;
}

export default function SourcesBar({
  sources,
  onSelectSource,
}: SourcesBarProps) {
  if (sources.length === 0) return null;

  return (
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
              onClick={() => onSelectSource(idx)}
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
  );
}
