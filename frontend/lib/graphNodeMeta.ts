export interface NodeBadge {
  label: string;
  className: string;
}

const SUBGRAPH_NODES = new Set([
  "query_rewrite",
  "retrieve_company",
  "grade_docs",
  "synthesize",
  "grade_answer",
]);

const NO_EXPAND_NODES = new Set(["synthesize", "retrieve_company"]);

const NODE_LABELS: Record<string, string> = {
  compress_context: "Compress Context",
  memory: "Memory",
  retrieve_decision: "Retrieve Decision",
  clarify: "Clarify",
  retrieval_agent: "Retrieval Agent",
  news_agent: "News Agent",
  calculator_agent: "Calculator Agent",
  aggregate: "Aggregate",
  guardrails: "Guardrails",
  fallback: "Fallback",
  answer: "Answer",
  query_rewrite: "↳ Query Rewrite",
  retrieve_company: "↳ Retrieve Company",
  grade_docs: "↳ Grade Docs",
  synthesize: "↳ Synthesise",
  grade_answer: "↳ Grade Answer",
};

export function getNodeLabel(node: string, status: "done" | "running"): string {
  if (node === "retrieval_agent") {
    return status === "running" ? "Retrieval Agent starts" : "Retrieval Agent ends";
  }
  return NODE_LABELS[node] ?? node;
}

export function isSubgraphNode(node: string): boolean {
  return SUBGRAPH_NODES.has(node);
}

export function canExpandNode(node: string, state?: Record<string, unknown>): boolean {
  return Boolean(state) && !NO_EXPAND_NODES.has(node);
}

export function getNodeBadges(
  node: string,
  status: "done" | "running",
  state?: Record<string, unknown>,
): NodeBadge[] {
  if (status !== "done" || !state) return [];

  if (node === "compress_context" && typeof state.compressed === "boolean") {
    return [{
      label: state.compressed ? "true" : "false",
      className: state.compressed
        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
        : "bg-[#e8f0fa] text-[#7a9ab8] dark:bg-[#0d1c2e] dark:text-[#3d5878]",
    }];
  }

  if (node === "retrieval_agent") {
    const companyStatus = (state.retrieval_result as { company_status?: Record<string, unknown> } | undefined)?.company_status;
    if (companyStatus && typeof companyStatus === "object") {
      return [{
        label: `(${Object.keys(companyStatus).length})`,
        className: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
      }];
    }
  }

  if (node === "grade_docs") {
    const count = (state.graded_docs as unknown[] | undefined)?.length ?? 0;
    return [{
      label: `${count} doc${count !== 1 ? "s" : ""} ${state.grade === "pass" ? "✓" : "✗"}`,
      className: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
    }];
  }

  if (node === "grade_answer") {
    const grounded = state.grounded as string | undefined;
    if (grounded === "yes") {
      return [{
        label: "verified",
        className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
      }];
    }
    if (grounded === "partial") {
      return [{
        label: "partial",
        className: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
      }];
    }
    if (grounded === "no") {
      return [{
        label: "unverified",
        className: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400",
      }];
    }
  }

  return [];
}
