"use client";

import type { MouseEvent } from "react";

interface ResizeHandleProps {
  side: "left" | "right";
  visible?: boolean;
  onMouseDown: (event: MouseEvent) => void;
}

export default function ResizeHandle({
  side,
  visible = true,
  onMouseDown,
}: ResizeHandleProps) {
  if (!visible) return null;

  return (
    <div
      onMouseDown={onMouseDown}
      className="hidden md:block w-1 shrink-0 cursor-col-resize group relative hover:bg-[#1a4a8a]/10 dark:hover:bg-[#c4880c]/10 transition-colors"
      title="Drag to resize"
    >
      <div className={`absolute inset-y-0 ${side === "left" ? "left-0" : "right-0"} w-px bg-[#cddcea] dark:bg-[#162840] group-hover:bg-[#1a4a8a] dark:group-hover:bg-[#c4880c] transition-colors`} />
    </div>
  );
}
