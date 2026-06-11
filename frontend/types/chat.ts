import type { ProgressCardData } from "@/components/ProgressCard";
import type { ChartSpec } from "@/lib/api";

export interface SourceItem {
  label: string;
  preview: string;
  source_type?: string;
  full_content?: string;
}

export interface Message {
  role: "user" | "assistant" | "system" | "progress";
  content: string;
  cards?: ProgressCardData[];
  chartData?: ChartSpec[];
  sources?: SourceItem[];
  confidence?: string;
  unsupportedClaims?: Array<{ claim: string; basis: string }>;
}
