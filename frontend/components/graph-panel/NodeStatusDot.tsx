interface NodeStatusDotProps {
  node: string;
  status: "done" | "running";
  isSubgraph: boolean;
}

export default function NodeStatusDot({
  node,
  status,
  isSubgraph,
}: NodeStatusDotProps) {
  const isRetrievalStarts = node === "retrieval_agent" && status === "running";

  if (isRetrievalStarts) {
    return <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 ring-1 ring-emerald-500/20" />;
  }

  if (status === "running") {
    return <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0 animate-pulse ring-2 ring-blue-500/20" />;
  }

  if (isSubgraph) {
    return <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0 ring-1 ring-blue-400/20" />;
  }

  return <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 ring-1 ring-emerald-500/20" />;
}
