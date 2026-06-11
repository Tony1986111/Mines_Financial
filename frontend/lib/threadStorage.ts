import type { Message } from "@/types/chat";
import type { GraphNodeEvent } from "@/types/graph";

export const ACTIVE_THREAD_KEY = "active_thread_id";

export interface StoredThread {
  id: string;
  label: string;
  updatedAt: number;
  messages: Message[];
  graphEvents?: GraphNodeEvent[];
}

export function loadThreads(): StoredThread[] {
  try {
    return JSON.parse(localStorage.getItem("chat_threads") ?? "[]");
  } catch {
    return [];
  }
}

export function saveThread(
  id: string,
  label: string,
  messages: Message[],
  graphEvents: GraphNodeEvent[],
) {
  const threads = loadThreads().filter(t => t.id !== id);
  threads.unshift({ id, label, updatedAt: Date.now(), messages, graphEvents });
  localStorage.setItem("chat_threads", JSON.stringify(threads.slice(0, 30)));
}

export function relativeTime(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
