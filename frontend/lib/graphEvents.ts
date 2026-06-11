import type { GraphNodeEvent } from "@/types/graph";

const MULTI_ENTRY_NODES = new Set(["retrieval_agent"]);

export function dedupEvents(events: GraphNodeEvent[]): GraphNodeEvent[] {
  const seen = new Set<string>();
  return events
    .filter((event) => {
      if (event.node === "__turn__" || MULTI_ENTRY_NODES.has(event.node)) return true;
      if (seen.has(event.node)) return false;
      seen.add(event.node);
      return true;
    })
    .map((event) => {
      if (event.node === "__turn__" || MULTI_ENTRY_NODES.has(event.node)) return event;
      const last = [...events].reverse().find((candidate) => candidate.node === event.node);
      return last ?? event;
    });
}
