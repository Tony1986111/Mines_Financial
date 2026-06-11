import BarChart from "@/components/BarChart";
import type { ChartSpec } from "@/lib/api";
import type { SourceItem } from "@/types/chat";

const SPLIT_RE = /(```[\s\S]*?```|\{\{chart:[^}]+\}\}|<sup class="citation"[^>]*>\[[^\]]+\]<\/sup>)/g;
const CHART_RE = /^\{\{chart:(.+)\}\}$/;
const SUP_RE = /^<sup class="citation"([^>]*)>(\[[^\]]+\])<\/sup>$/;

export function renderContent({
  text,
  chartData,
  sources,
}: {
  text: string;
  chartData?: ChartSpec[];
  sources?: SourceItem[];
}) {
  const chartMap = new Map<string, ChartSpec>();
  if (chartData) {
    for (const chart of chartData) {
      chartMap.set(chart.title.split(" (")[0], chart);
    }
  }

  const parts = text.split(SPLIT_RE);
  return parts.map((part, i) => {
    if (part.startsWith("```")) {
      const code = part.replace(/^```[^\n]*\n?/, "").replace(/```$/, "");
      return (
        <pre key={i} className="mt-2 mb-1 bg-[#060c14] dark:bg-[#030810] rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre border border-[#162840] text-[#8ab8e8]">
          {code}
        </pre>
      );
    }

    const chartMatch = part.match(CHART_RE);
    if (chartMatch) {
      const spec = chartMap.get(chartMatch[1]);
      return spec ? <BarChart key={i} spec={spec} /> : null;
    }

    const supMatch = part.match(SUP_RE);
    if (supMatch) {
      const numText = supMatch[2];
      const allNums = numText.slice(1, -1)
        .split(",")
        .map(value => parseInt(value.trim(), 10))
        .filter(value => !isNaN(value) && value >= 1)
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
