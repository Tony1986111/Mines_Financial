import GraphTurnDivider from "@/components/graph-panel/GraphTurnDivider";
import NodeRow from "@/components/graph-panel/NodeRow";
import { dedupEvents } from "@/lib/graphEvents";
import type { GraphNodeEvent } from "@/types/graph";

interface GraphEventListProps {
  events: GraphNodeEvent[];
}

export default function GraphEventList({ events }: GraphEventListProps) {
  return (
    <div className="flex-1 overflow-y-auto py-2">
      {events.length === 0 ? (
        <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] italic text-center mt-6 px-4">
          Graph progress will appear here when you send a message.
        </p>
      ) : (
        <div className="space-y-0.5 px-1">
          {dedupEvents(events).map((event, i) =>
            event.node === "__turn__" ? (
              <GraphTurnDivider
                key={i}
                query={event.state?.query}
              />
            ) : (
              <NodeRow
                key={`${event.node}-${i}`}
                node={event.node}
                status={event.status}
                state={event.state}
              />
            )
          )}
        </div>
      )}
    </div>
  );
}
