import GraphPanelLinks from "@/components/graph-panel/GraphPanelLinks";

interface GraphPanelHeaderProps {
  visible: boolean;
  onToggle: () => void;
}

export default function GraphPanelHeader({
  visible,
  onToggle,
}: GraphPanelHeaderProps) {
  return (
    <div className="h-12 flex items-center border-b border-[#cddcea] dark:border-[#162840] shrink-0 px-2">
      <button
        onClick={onToggle}
        title={visible ? "Hide graph panel" : "Show graph panel"}
        className="w-6 h-6 flex items-center justify-center rounded text-[#7a9ab8] dark:text-[#3d5878] hover:text-[#1a4a8a] dark:hover:text-[#7aade8] hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] transition-colors text-xs"
      >
        {visible ? "›" : "‹"}
      </button>
      {visible && (
        <>
          <span className="ml-2 text-xs font-bold tracking-wide text-[#0a1e38] dark:text-[#c4d8f0]">
            Graph Progress
          </span>
          <GraphPanelLinks />
        </>
      )}
    </div>
  );
}
