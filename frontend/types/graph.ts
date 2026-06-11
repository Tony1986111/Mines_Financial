export interface GraphNodeEvent {
  node: string;
  status: "done" | "running";
  state?: Record<string, unknown>;
}
