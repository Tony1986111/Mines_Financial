const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ChatResponse {
  thread_id: string;
  answer: string;
  interrupted: boolean;
  clarification_question: string | null;
}

export interface GraphMermaidResponse {
  diagram: string;
}

// ── SSE event types from /api/chat/stream ─────────────────────────────────────

export interface NodeStartEvent {
  type: "node_start";
  node: string;
}

export interface NodeDoneEvent {
  type: "node_done";
  node: string;
  state: Record<string, unknown>;
}

export interface InterruptEvent {
  type: "interrupt";
  question: string;
}

export interface ChartDataset {
  label: string;
  data: (number | null)[];
}

export interface ChartSpec {
  type: "bar";
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

export interface SourceRef {
  label: string;
  preview: string;
  source_type?: string;
  full_content?: string;
}

export interface DoneEvent {
  type: "done";
  answer: string;
  chart_data?: ChartSpec[];
  sources?: SourceRef[];
  confidence?: string;
  unsupported_claims?: Array<{ claim: string; basis: string }>;
}

export interface ErrorEvent {
  type: "error";
  detail: string;
}

export type StreamEvent = NodeStartEvent | NodeDoneEvent | InterruptEvent | DoneEvent | ErrorEvent;

// ── API functions ──────────────────────────────────────────────────────────────

export interface ThreadMeta {
  id: string;
  label: string;
  updated_at: string | null;
}

export async function fetchThreads(): Promise<ThreadMeta[]> {
  try {
    const res = await fetch(`${API_BASE}/api/threads`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function deleteThread(threadId: string): Promise<void> {
  await fetch(`${API_BASE}/api/threads/${threadId}`, { method: "DELETE" });
}

export async function createThread(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/threads`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to create thread");
  const data = await res.json();
  return data.thread_id;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ProgressTurn {
  turn_index: number;
  cards: unknown[];
}

export function saveProgress(threadId: string, turnIndex: number, cards: unknown[]): void {
  fetch(`${API_BASE}/api/threads/${threadId}/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ turn_index: turnIndex, cards }),
  }).catch(() => {});
}

export async function fetchProgress(threadId: string): Promise<ProgressTurn[]> {
  try {
    const res = await fetch(`${API_BASE}/api/threads/${threadId}/progress`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchThreadHistory(threadId: string): Promise<HistoryMessage[]> {
  try {
    const res = await fetch(`${API_BASE}/api/threads/${threadId}/history`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

// ── Semantic memory (conclusions) ─────────────────────────────────────────────

export interface Conclusion {
  id: string;
  query: string;
  answer: string;
  companies: string;
  fy: string;
}

export async function fetchConclusions(): Promise<Conclusion[]> {
  const res = await fetch(`${API_BASE}/api/memory/conclusions`);
  if (!res.ok) return [];
  return res.json();
}

export async function updateConclusion(id: string, answer: string): Promise<void> {
  await fetch(`${API_BASE}/api/memory/conclusions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
}

export async function deleteConclusion(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/memory/conclusions/${id}`, { method: "DELETE" });
}

export async function fetchGraphMermaid(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/graph/mermaid`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  const data = await res.json() as GraphMermaidResponse;
  return data.diagram;
}

export async function sendMessage(
  threadId: string,
  message: string,
  resume = false
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message, resume }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Stream graph execution events from /api/chat/stream.
 * Calls onEvent for each SSE event until the stream ends or errors.
 */
export async function streamMessage(
  threadId: string,
  message: string,
  resume: boolean,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const url = `${API_BASE}/api/chat/stream`;
  console.log("[streamMessage] fetching", url, { threadId, resume });

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message, resume }),
  });

  console.log("[streamMessage] response status:", res.status, res.ok);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lineCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    console.log("[streamMessage] read chunk: done=", done, "bytes=", value?.length ?? 0);
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        lineCount++;
        try {
          const event = JSON.parse(line.slice(6)) as StreamEvent;
          console.log(`[streamMessage] event #${lineCount}:`, event.type, "node" in event ? (event as {node:string}).node : "");
          onEvent(event);
        } catch (e) {
          console.warn("[streamMessage] failed to parse line:", line, e);
        }
      }
    }
  }
  console.log("[streamMessage] stream ended, total events:", lineCount);
}
