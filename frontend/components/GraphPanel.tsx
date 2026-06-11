"use client";

import GraphEventList from "@/components/graph-panel/GraphEventList";
import GraphPanelHeader from "@/components/graph-panel/GraphPanelHeader";
import type { GraphNodeEvent } from "@/types/graph";

export type { GraphNodeEvent } from "@/types/graph";

interface GraphPanelProps {
  events: GraphNodeEvent[];
  visible: boolean;
  width: number;
  onToggle: () => void;
}

export default function GraphPanel({
  events,
  visible,
  width,
  onToggle,
}: GraphPanelProps) {
  return (
    <aside
      className="shrink-0 flex flex-col border-l border-[#cddcea] dark:border-[#162840] bg-[#f4f8fd] dark:bg-[#091524]"
      style={{ width: visible ? `min(${width}px, 100vw)` : 36 }}
    >
      <GraphPanelHeader visible={visible} onToggle={onToggle} />
      {visible && <GraphEventList events={events} />}
    </aside>
  );
}
