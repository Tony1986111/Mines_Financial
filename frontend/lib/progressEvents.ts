import { type ProgressCardData } from "@/components/ProgressCard";

const HIDDEN_NODES = new Set(["memory", "aggregate", "guardrails"]);

export const MOBILE_PROGRESS_LABELS: Record<string, string> = {
  compress_context: "Compressing",
  memory: "Memory",
  retrieve_decision: "Routing",
  clarify: "Clarifying",
  retrieval_agent: "Searching reports",
  news_agent: "Searching news",
  calculator_agent: "Calculating",
  aggregate: "Combining",
  guardrails: "Checking",
  fallback: "Fallback",
  answer: "Answering",
  query_rewrite: "Rewriting query",
  retrieve_company: "Retrieving docs",
  grade_docs: "Grade Docs",
  synthesize: "Synthesising",
  grade_answer: "Verifying answer",
};

export function toCards(v: ProgressCardData | ProgressCardData[] | null): ProgressCardData[] {
  if (v === null) return [];
  return Array.isArray(v) ? v : [v];
}

export function nodeEventToCard(
  node: string,
  status: "running" | "done",
  state?: Record<string, unknown>,
): ProgressCardData | ProgressCardData[] | null {
  if (HIDDEN_NODES.has(node)) return null;

  if (status === "running") {
    const texts: Record<string, string> = {
      retrieve_decision: "Analysing question type...",
      // retrieval_agent and news_agent are pre-announced by retrieve_decision done;
      // returning null here prevents node_start from moving that card to the end.
      calculator_agent: "Calculating financial metrics...",
      grade_docs: "Grading retrieved documents...",
      answer: "Generating answer...",
    };
    const text = texts[node];
    return text ? { id: node, status: "running", variant: "status", text } : null;
  }

  if (node === "retrieve_decision") {
    if (state?.needs_retrieval === false && !state?.needs_news) {
      return {
        id: node,
        status: "done",
        variant: "direct",
        text: "Answering directly from memory, no report lookup needed.",
      };
    }
    const cards: ProgressCardData[] = [];
    if (state?.needs_retrieval !== false) {
      cards.push({
        id: "retrieval_agent",
        status: "running",
        variant: "status",
        text: "Searching financial reports...",
      });
    }
    if (state?.needs_news) {
      cards.push({
        id: "news_agent",
        status: "running",
        variant: "status",
        text: "Searching latest news...",
      });
    }
    return cards.length > 0 ? cards : null;
  }

  if (node === "retrieval_agent") {
    const docs =
      ((state?.retrieval_result as { documents?: unknown[] } | undefined)?.documents) ?? [];
    const count = docs.length;
    const breakdown: Record<string, number> = {};
    for (const doc of docs as Record<string, unknown>[]) {
      const company = String(doc.company ?? "Unknown");
      const fy = String(doc.fy ?? "");
      const key = fy ? `${company} ${fy}` : company;
      breakdown[key] = (breakdown[key] ?? 0) + 1;
    }
    const bodyLines = Object.entries(breakdown).map(([k, v]) => `${k} (${v})`);
    return {
      id: node,
      status: "done",
      variant: "result",
      icon: "📄",
      title: `Found ${count} relevant passage${count !== 1 ? "s" : ""}`,
      bodyLines: bodyLines.length > 0 ? bodyLines : undefined,
    };
  }

  if (node === "news_agent") {
    const hasNews =
      typeof state?.news_context === "string" &&
      (state.news_context as string).trim().length > 0;
    return {
      id: node,
      status: "done",
      variant: "result",
      icon: "📰",
      title: hasNews ? "Found relevant news articles" : "No recent news found",
    };
  }

  if (node === "calculator_agent") {
    const calcResult = state?.calc_result as string | undefined;
    return {
      id: node,
      status: "done",
      variant: "result",
      icon: "🔢",
      title: "Calculation result",
      bodyLines: calcResult ? [calcResult] : undefined,
    };
  }

  if (node === "compress_context") {
    const messages = (state?.messages as { type: string; content: string }[] | undefined) ?? [];
    const summaryMsg = messages.find(
      m => typeof m.content === "string" && m.content.startsWith("[Earlier conversation compressed]:"),
    );
    if (!summaryMsg) return null;
    const summary = summaryMsg.content.replace("[Earlier conversation compressed]:", "").trim();
    return {
      id: node,
      status: "done",
      variant: "result",
      icon: "🗜️",
      title: "Context compressed - click to view summary",
      expandBody: summary,
    };
  }

  if (node === "fallback") {
    return {
      id: node,
      status: "done",
      variant: "fallback",
      text: "⚠️ No data can be found from the available annual reports.",
    };
  }

  if (node === "query_rewrite") {
    const callIdx = (state?._call_idx as number | undefined) ?? 0;
    const isRetry = callIdx > 0;
    if (isRetry) {
      const companyQueries =
        (state?.company_queries as { company: string; query: string }[] | undefined) ?? [];
      const bodyLines = companyQueries.map(cq => `${cq.company}: ${cq.query}`);
      return {
        id: `query_rewrite_${callIdx}`,
        status: "done",
        variant: "result",
        icon: "🔄",
        title: "Retrying with targeted queries",
        bodyLines: bodyLines.length > 0 ? bodyLines : undefined,
      };
    }
    const rewritten = state?.rewritten_query as string | undefined;
    return {
      id: `query_rewrite_${callIdx}`,
      status: "done",
      variant: "result",
      icon: "🔍",
      title: "Query rewritten",
      bodyLines: rewritten ? [rewritten] : undefined,
    };
  }

  if (node === "retrieve_company") {
    return null;
  }

  if (node === "grade_docs") {
    const callIdx = (state?._call_idx as number | undefined) ?? 0;
    const retrieved = (state?.retrieved_count as number | undefined) ?? 0;
    const graded = (state?.graded_docs as unknown[] | undefined) ?? [];
    if (retrieved === 0) return null;
    const docGrade = state?.grade as string | undefined;
    return {
      id: `grade_docs_${callIdx}`,
      status: "done",
      variant: "result",
      icon: docGrade === "pass" ? "✅" : "⚠️",
      title: `Retrieved ${retrieved} chunk${retrieved !== 1 ? "s" : ""} - ${graded.length} passed relevance check`,
    };
  }

  if (node === "synthesize") {
    const callIdx = (state?._call_idx as number | undefined) ?? 0;
    return {
      id: `synthesize_${callIdx}`,
      status: "done",
      variant: "result",
      icon: "✍️",
      title: "Answer drafted",
    };
  }

  if (node === "grade_answer") {
    const callIdx = (state?._call_idx as number | undefined) ?? 0;
    const grounded = state?.grounded as string | undefined;
    const hints = (state?.unsupported_hints as string[] | undefined) ?? [];
    if (hints.length >= 2) {
      const detail = ": " + hints.slice(0, 2).join(", ");
      return {
        id: `grade_answer_${callIdx}`,
        status: "done",
        variant: "fallback",
        text: `⚠️ Unverified claims - retrying${detail}`,
      };
    }
    if (grounded === "partial") {
      return {
        id: `grade_answer_${callIdx}`,
        status: "done",
        variant: "result",
        icon: "🟡",
        title: "Answer partially verified",
      };
    }
    return {
      id: `grade_answer_${callIdx}`,
      status: "done",
      variant: "result",
      icon: "✅",
      title: "Answer verified",
    };
  }

  return null;
}
