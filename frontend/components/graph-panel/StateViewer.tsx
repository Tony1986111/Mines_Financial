import StateValue from "@/components/graph-panel/StateValue";

interface StateViewerProps {
  state: Record<string, unknown>;
}

export default function StateViewer({ state }: StateViewerProps) {
  const entries = Object.entries(state).filter(([key]) => !key.startsWith("_"));

  return (
    <div className="mt-2 space-y-1 text-xs font-mono bg-[#eef4fb] dark:bg-[#060c14] border border-[#cddcea] dark:border-[#162840] rounded-lg p-3 max-h-72 overflow-y-auto">
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-2 items-start">
          <span className="text-[#1a4a8a] dark:text-[#7aade8] shrink-0 font-semibold">{key}:</span>
          <StateValue value={value} />
        </div>
      ))}
    </div>
  );
}
