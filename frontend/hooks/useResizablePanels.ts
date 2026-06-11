"use client";

import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";

const LEFT_WIDTH_KEY = "sidebar_left_width";
const RIGHT_WIDTH_KEY = "sidebar_right_width";

const LEFT_MIN = 160;
const LEFT_MAX = 480;
const RIGHT_MIN = 200;
const RIGHT_MAX = 560;

type DragState = {
  side: "left" | "right";
  startX: number;
  startWidth: number;
};

export function useResizablePanels() {
  const [leftWidth, setLeftWidth] = useState(256);
  const [rightWidth, setRightWidth] = useState(288);
  const dragging = useRef<DragState | null>(null);

  useEffect(() => {
    const lw = parseInt(localStorage.getItem(LEFT_WIDTH_KEY) ?? "");
    const rw = parseInt(localStorage.getItem(RIGHT_WIDTH_KEY) ?? "");
    if (!isNaN(lw) && lw >= LEFT_MIN) setLeftWidth(lw);
    if (!isNaN(rw) && rw >= RIGHT_MIN) setRightWidth(rw);
  }, []);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!dragging.current) return;
      const { side, startX, startWidth } = dragging.current;
      if (side === "left") {
        setLeftWidth(Math.max(LEFT_MIN, Math.min(LEFT_MAX, startWidth + e.clientX - startX)));
      } else {
        setRightWidth(Math.max(RIGHT_MIN, Math.min(RIGHT_MAX, startWidth - (e.clientX - startX))));
      }
    }

    function onMouseUp(e: MouseEvent) {
      if (!dragging.current) return;
      const { side, startX, startWidth } = dragging.current;
      if (side === "left") {
        const w = Math.max(LEFT_MIN, Math.min(LEFT_MAX, startWidth + e.clientX - startX));
        localStorage.setItem(LEFT_WIDTH_KEY, String(w));
      } else {
        const w = Math.max(RIGHT_MIN, Math.min(RIGHT_MAX, startWidth - (e.clientX - startX)));
        localStorage.setItem(RIGHT_WIDTH_KEY, String(w));
      }
      dragging.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  const startDrag = useCallback((side: "left" | "right", e: ReactMouseEvent) => {
    dragging.current = {
      side,
      startX: e.clientX,
      startWidth: side === "left" ? leftWidth : rightWidth,
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  }, [leftWidth, rightWidth]);

  return { leftWidth, rightWidth, startDrag };
}
