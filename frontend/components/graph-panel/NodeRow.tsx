"use client";

import { useState } from "react";
import NodeBadges from "@/components/graph-panel/NodeBadges";
import NodeStatusDot from "@/components/graph-panel/NodeStatusDot";
import QueryRewriteDetails from "@/components/graph-panel/QueryRewriteDetails";
import StateViewer from "@/components/graph-panel/StateViewer";
import { canExpandNode, getNodeBadges, getNodeLabel, isSubgraphNode } from "@/lib/graphNodeMeta";

interface NodeRowProps {
  node: string;
  status: "done" | "running";
  state?: Record<string, unknown>;
}

export default function NodeRow({ node, status, state }: NodeRowProps) {
  const [expanded, setExpanded] = useState(false);
  const label = getNodeLabel(node, status);
  const isSubgraph = isSubgraphNode(node);
  const canExpand = canExpandNode(node, state);
  const badges = getNodeBadges(node, status, state);

  return (
    <div>
      <button
        onClick={() => canExpand && setExpanded(current => !current)}
        disabled={!canExpand}
        className={`w-full flex items-center gap-2.5 rounded-lg text-left transition-colors ${
          isSubgraph ? "px-7 py-2" : "px-3 py-2"
        } ${
          canExpand ? "hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] cursor-pointer" : "cursor-default"
        }`}
      >
        <NodeStatusDot node={node} status={status} isSubgraph={isSubgraph} />

        <span className={`text-xs font-medium flex-1 ${
          status === "running"
            ? "text-blue-600 dark:text-blue-400"
            : isSubgraph
            ? "text-blue-700 dark:text-blue-300"
            : "text-[#0a1e38] dark:text-[#c4d8f0]"
        }`}>
          {label}
        </span>

        <NodeBadges badges={badges} />

        {canExpand && (
          <span className="text-[10px] text-[#7a9ab8] dark:text-[#3d5878]">
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </button>

      {expanded && canExpand && state && (
        <div className="px-3 pb-2">
          {node === "query_rewrite" ? (
            <QueryRewriteDetails state={state} />
          ) : (
            <StateViewer state={state} />
          )}
        </div>
      )}
    </div>
  );
}
