import type { Message } from "@/types/chat";
import type { SourceRef } from "@/lib/api";

export function extractSourcesFromContent(content: string): SourceRef[] {
  const match = content.match(/\n\nSources:\n([\s\S]+)$/);
  if (!match) return [];
  const sources: SourceRef[] = [];
  for (const line of match[1].trim().split("\n")) {
    const m = line.match(/^\[(\d+)\]\s+(.+)$/);
    if (m) sources.push({ label: m[2].trim(), preview: "" });
  }
  return sources;
}

export function enrichMessages(msgs: Message[]): Message[] {
  return msgs.map(m => {
    if (m.role !== "assistant") return m;
    if (m.sources && m.sources.length > 0) return m;
    const extracted = extractSourcesFromContent(m.content);
    return extracted.length > 0 ? { ...m, sources: extracted } : m;
  });
}
