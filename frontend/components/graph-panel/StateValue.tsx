"use client";

import { useState } from "react";

interface StateValueProps {
  value: unknown;
}

export default function StateValue({ value }: StateValueProps) {
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
        onClick={() => setOpen(current => !current)}
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
          onClick={() => setOpen(current => !current)}
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
          onClick={() => setOpen(current => !current)}
          className="text-[#1a4a8a] dark:text-[#7aade8] hover:underline font-mono text-xs"
        >
          {open ? "▼" : "▶"} {"{"}…{"}"}
        </button>
        {open && (
          <div className="ml-4 mt-1 border-l border-[#162840] pl-2 space-y-0.5">
            {entries.map(([key, nestedValue]) => (
              <div key={key} className="flex gap-1.5 text-xs">
                <span className="text-[#7a9ab8] shrink-0 font-mono">{key}:</span>
                <StateValue value={nestedValue} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  return <span className="text-[#0a1e38] dark:text-[#c4d8f0] text-xs">{String(value)}</span>;
}
